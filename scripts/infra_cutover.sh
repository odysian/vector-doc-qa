#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DEFAULT_TF_DIR="${REPO_ROOT}/infra/terraform"
DEFAULT_TFVARS="envs/prod.tfvars"
DEFAULT_HEALTH_URL="https://api.quaero.odysian.dev/health"

print_usage() {
  cat <<'EOF'
Usage:
  scripts/infra_cutover.sh <prepare|postcheck> [options]

Commands:
  prepare    Snapshot checkpoint + terraform checks/plan + evidence draft output.
  postcheck  Run post-cutover health gates and optional ops-agent/bootstrap checks.

prepare options:
  --tf-dir <path>         Terraform directory (default: infra/terraform)
  --tfvars <path>         Terraform var-file path (default: envs/prod.tfvars)
  --project <id>          GCP project ID (defaults from tfvars project_id)
  --zone <zone>           GCP zone (defaults from tfvars zone)
  --instance <name>       VM instance name (defaults from tfvars vm_name)
  --skip-snapshot         Skip pre-cutover disk snapshot creation
  --pin-image-family      Resolve vm_image family to exact image self-link and write it back to tfvars
  --snapshot-id <name>    Snapshot id override
  --evidence-file <path>  Evidence draft output path (default: /tmp/quaero-cutover-<ts>.md)
  --plan-output <path>    Terraform plan output path (default: /tmp/quaero-cutover-plan-<ts>.txt)

postcheck options:
  --health-url <url>      Health endpoint (default: https://api.quaero.odysian.dev/health)
  --checks <n>            Consecutive checks required (default: 15)
  --interval <seconds>    Interval between checks (default: 10)
  --baseline-min <num>    Baseline bootstrap minutes (optional)
  --post-min <num>        Post-cutover bootstrap minutes (optional)
  --ops-agent-gate        Run 10-minute no-restart ops-agent gate over gcloud SSH
  --tfvars <path>         Terraform var-file path used for project/zone/instance defaults
  --project <id>          GCP project ID (defaults from tfvars project_id)
  --zone <zone>           GCP zone (defaults from tfvars zone)
  --instance <name>       VM instance name (defaults from tfvars vm_name)

Examples:
  scripts/infra_cutover.sh prepare --tfvars envs/prod.tfvars
  scripts/infra_cutover.sh postcheck --ops-agent-gate --baseline-min 10 --post-min 5.8
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

is_true() {
  case "${1:-}" in
    1|true|TRUE|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

read_tfvar() {
  local key="$1"
  local tfvars_path="$2"

  awk -v key="$key" '
    $0 ~ "^[[:space:]]*" key "[[:space:]]*=" {
      line = $0
      sub(/^[[:space:]]*[^=]+=[[:space:]]*/, "", line)
      sub(/[[:space:]]*#.*/, "", line)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
      if (line ~ /^".*"$/) {
        line = substr(line, 2, length(line) - 2)
      }
      value = line
    }
    END {
      if (value != "") {
        print value
      }
    }
  ' "$tfvars_path"
}

assert_numeric() {
  local value="$1"
  local label="$2"
  [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "$label must be numeric, got: $value"
}

prepare_cutover() {
  require_cmd git
  require_cmd terraform
  require_cmd gcloud
  require_cmd rg
  require_cmd sha256sum

  local tf_dir="$DEFAULT_TF_DIR"
  local tfvars="$DEFAULT_TFVARS"
  local project_override=""
  local zone_override=""
  local instance_override=""
  local skip_snapshot="false"
  local pin_image_family="false"
  local snapshot_id_override=""
  local evidence_file_override=""
  local plan_output_override=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --tf-dir) tf_dir="$2"; shift 2 ;;
      --tfvars) tfvars="$2"; shift 2 ;;
      --project) project_override="$2"; shift 2 ;;
      --zone) zone_override="$2"; shift 2 ;;
      --instance) instance_override="$2"; shift 2 ;;
      --skip-snapshot) skip_snapshot="true"; shift ;;
      --pin-image-family) pin_image_family="true"; shift ;;
      --snapshot-id) snapshot_id_override="$2"; shift 2 ;;
      --evidence-file) evidence_file_override="$2"; shift 2 ;;
      --plan-output) plan_output_override="$2"; shift 2 ;;
      -h|--help) print_usage; exit 0 ;;
      *) die "Unknown option for prepare: $1" ;;
    esac
  done

  [[ "$tf_dir" = /* ]] || tf_dir="${REPO_ROOT}/${tf_dir}"
  [[ -d "$tf_dir" ]] || die "Terraform directory not found: $tf_dir"

  local tfvars_path="$tfvars"
  if [[ "$tfvars_path" != /* ]]; then
    tfvars_path="${tf_dir}/${tfvars_path}"
  fi
  [[ -f "$tfvars_path" ]] || die "tfvars file not found: $tfvars_path"

  local timestamp
  timestamp="$(date -u +%Y%m%d-%H%M%S)"
  local plan_output="${plan_output_override:-/tmp/quaero-cutover-plan-${timestamp}.txt}"
  local evidence_file="${evidence_file_override:-/tmp/quaero-cutover-evidence-${timestamp}.md}"

  local infra_commit_sha project_id zone instance_name vm_image reconcile_release_id
  infra_commit_sha="$(git -C "$REPO_ROOT" rev-parse HEAD)"

  project_id="${project_override:-$(read_tfvar "project_id" "$tfvars_path")}"
  zone="${zone_override:-$(read_tfvar "zone" "$tfvars_path")}"
  instance_name="${instance_override:-$(read_tfvar "vm_name" "$tfvars_path")}"
  vm_image="$(read_tfvar "vm_image" "$tfvars_path")"
  reconcile_release_id="$(read_tfvar "reconcile_release_id" "$tfvars_path")"

  [[ -n "$project_id" ]] || die "project_id not found (set --project or add project_id in tfvars)"
  [[ -n "$zone" ]] || die "zone not found (set --zone or add zone in tfvars)"
  [[ -n "$instance_name" ]] || die "vm_name not found (set --instance or add vm_name in tfvars)"
  [[ -n "$vm_image" ]] || die "vm_image must be set in tfvars for deterministic cutover"
  [[ -n "$reconcile_release_id" ]] || die "reconcile_release_id must be set in tfvars"

  [[ "$vm_image" == *"/global/images/"* ]] || die "vm_image must be an exact image self-link under /global/images/"
  if [[ "$vm_image" == *"/global/images/family/"* ]]; then
    local family_name family_project resolved_image
    family_name="$(printf '%s' "$vm_image" | sed -n 's|.*/global/images/family/\([^/]*\)$|\1|p')"
    family_project="$(printf '%s' "$vm_image" | sed -n 's|.*projects/\([^/]*\)/global/images/family/.*|\1|p')"
    family_project="${family_project:-$project_id}"
    resolved_image=""
    if [[ -n "$family_name" && -n "$family_project" ]]; then
      resolved_image="$(
        gcloud compute images describe-from-family "$family_name" \
          --project "$family_project" \
          --format='value(selfLink)' 2>/dev/null || true
      )"
    fi

    if [[ -n "$resolved_image" ]]; then
      if is_true "$pin_image_family"; then
        perl -0pi -e 's|^vm_image\s*=\s*"[^"]*"|vm_image       = "'"$resolved_image"'"|m' "$tfvars_path"
        vm_image="$resolved_image"
        echo "Pinned vm_image in tfvars to exact image self-link: $vm_image"
      else
        die "vm_image uses mutable family reference. Pin exact image self-link in tfvars, or rerun with --pin-image-family. Suggested value: vm_image = \"$resolved_image\""
      fi
    else
      die "vm_image uses mutable family reference and could not resolve exact image. Pin exact image self-link in tfvars before cutover."
    fi
  fi

  local snapshot_id="" disk_name=""
  if ! is_true "$skip_snapshot"; then
    disk_name="$(
      gcloud compute instances describe "$instance_name" \
        --project "$project_id" \
        --zone "$zone" \
        --format='value(disks[0].source.basename())'
    )"
    [[ -n "$disk_name" ]] || die "Unable to resolve boot disk for instance: $instance_name"
    snapshot_id="${snapshot_id_override:-${instance_name}-pre-cutover-${timestamp}}"
    gcloud compute disks snapshot "$disk_name" \
      --project "$project_id" \
      --zone "$zone" \
      --snapshot-names "$snapshot_id"
  fi

  terraform -chdir="$tf_dir" fmt -check
  terraform -chdir="$tf_dir" validate
  terraform -chdir="$tf_dir" plan -no-color -var-file="$tfvars_path" | tee "$plan_output"

  local reconcile_sha256 reconcile_sha256_source
  reconcile_sha256="$(
    rg -o 'reconcile_sha256"[[:space:]]*=[[:space:]]*"[0-9a-f]{64}"' "$plan_output" \
      | rg -o '[0-9a-f]{64}' \
      | head -n1 || true
  )"
  if [[ -n "$reconcile_sha256" ]]; then
    reconcile_sha256_source="plan"
  else
    reconcile_sha256="$(sha256sum "${tf_dir}/scripts/reconcile.sh" | awk '{print $1}')"
    reconcile_sha256_source="local-reconcile.sh"
  fi

  cat > "$evidence_file" <<EOF
# Cutover Evidence Draft (Generated ${timestamp} UTC)

- infra_commit_sha: ${infra_commit_sha}
- target vm_image: ${vm_image}
- target reconcile_release_id: ${reconcile_release_id}
- target reconcile_sha256: ${reconcile_sha256}
- reconcile_sha256 source: ${reconcile_sha256_source}
- terraform tfvars: ${tfvars_path}
- terraform plan output: ${plan_output}
- checkpoint snapshot id: ${snapshot_id:-<skipped>}

Fill these before close:
- UTC window: <required>
- Named owner signoff: <required>
- Baseline bootstrap time (minutes): <required>
- Previous rollback tuple (vm_image, reconcile_release_id): <required>
- Previous determinism pins (infra_commit_sha, reconcile_sha256): <required>
- Non-prod rollback rehearsal evidence link: <required>
EOF

  cat <<EOF
Prepare complete.
  infra_commit_sha: ${infra_commit_sha}
  project_id: ${project_id}
  zone: ${zone}
  instance: ${instance_name}
  vm_image: ${vm_image}
  reconcile_release_id: ${reconcile_release_id}
  reconcile_sha256 (${reconcile_sha256_source}): ${reconcile_sha256}
  snapshot_id: ${snapshot_id:-<skipped>}
  plan_output: ${plan_output}
  evidence_file: ${evidence_file}
EOF
}

run_ops_agent_gate() {
  local project_id="$1"
  local zone="$2"
  local instance_name="$3"
  require_cmd gcloud

  local remote_cmd
  remote_cmd='set -euo pipefail
sudo systemctl is-active --quiet google-cloud-ops-agent
before="$(sudo systemctl show google-cloud-ops-agent -p NRestarts --value)"
sleep 600
after="$(sudo systemctl show google-cloud-ops-agent -p NRestarts --value)"
test "$before" = "$after"
sudo systemctl status google-cloud-ops-agent --no-pager'

  gcloud compute ssh "$instance_name" \
    --project "$project_id" \
    --zone "$zone" \
    --command "$remote_cmd"
}

postcheck_cutover() {
  require_cmd curl
  require_cmd awk

  local health_url="$DEFAULT_HEALTH_URL"
  local checks=15
  local interval=10
  local baseline_min=""
  local post_min=""
  local run_ops_gate="false"
  local tfvars="$DEFAULT_TFVARS"
  local project_override=""
  local zone_override=""
  local instance_override=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --health-url) health_url="$2"; shift 2 ;;
      --checks) checks="$2"; shift 2 ;;
      --interval) interval="$2"; shift 2 ;;
      --baseline-min) baseline_min="$2"; shift 2 ;;
      --post-min) post_min="$2"; shift 2 ;;
      --ops-agent-gate) run_ops_gate="true"; shift ;;
      --tfvars) tfvars="$2"; shift 2 ;;
      --project) project_override="$2"; shift 2 ;;
      --zone) zone_override="$2"; shift 2 ;;
      --instance) instance_override="$2"; shift 2 ;;
      -h|--help) print_usage; exit 0 ;;
      *) die "Unknown option for postcheck: $1" ;;
    esac
  done

  [[ "$checks" =~ ^[0-9]+$ ]] || die "--checks must be an integer"
  [[ "$interval" =~ ^[0-9]+$ ]] || die "--interval must be an integer"

  for i in $(seq 1 "$checks"); do
    curl -fsS "$health_url" >/dev/null || die "Health gate failed at check ${i}/${checks}"
    echo "health gate ${i}/${checks} passed"
    if [[ "$i" -lt "$checks" ]]; then
      sleep "$interval"
    fi
  done

  if is_true "$run_ops_gate"; then
    local tfvars_path="$tfvars"
    if [[ "$tfvars_path" != /* ]]; then
      tfvars_path="${DEFAULT_TF_DIR}/${tfvars_path}"
    fi
    [[ -f "$tfvars_path" ]] || die "tfvars file not found: $tfvars_path"

    local project_id zone instance_name
    project_id="${project_override:-$(read_tfvar "project_id" "$tfvars_path")}"
    zone="${zone_override:-$(read_tfvar "zone" "$tfvars_path")}"
    instance_name="${instance_override:-$(read_tfvar "vm_name" "$tfvars_path")}"
    [[ -n "$project_id" ]] || die "project_id required for --ops-agent-gate"
    [[ -n "$zone" ]] || die "zone required for --ops-agent-gate"
    [[ -n "$instance_name" ]] || die "instance name required for --ops-agent-gate"
    run_ops_agent_gate "$project_id" "$zone" "$instance_name"
  fi

  if [[ -n "$baseline_min" || -n "$post_min" ]]; then
    [[ -n "$baseline_min" && -n "$post_min" ]] || die "Provide both --baseline-min and --post-min"
    assert_numeric "$baseline_min" "baseline-min"
    assert_numeric "$post_min" "post-min"

    local strict_target_min
    strict_target_min="$(
      awk -v b="$baseline_min" 'BEGIN { t=b*0.6; if (t < 6) printf "%.2f", t; else printf "6.00" }'
    )"
    awk -v post="$post_min" -v target="$strict_target_min" '
      BEGIN {
        if (post <= target) {
          printf "bootstrap_target_met=true (post=%s, target=%s)\n", post, target
          exit 0
        }
        printf "bootstrap_target_met=false (post=%s, target=%s)\n", post, target
        exit 1
      }
    '
  fi

  echo "Postcheck complete."
}

main() {
  [[ $# -ge 1 ]] || {
    print_usage
    exit 1
  }

  local command="$1"
  shift

  case "$command" in
    prepare) prepare_cutover "$@" ;;
    postcheck) postcheck_cutover "$@" ;;
    -h|--help|help) print_usage ;;
    *) die "Unknown command: $command" ;;
  esac
}

main "$@"
