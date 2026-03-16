# Terraform input contract for backend infrastructure and cutover automation.
# Includes determinism/security guards for SSH ingress, pinned agent versions, and OIDC identity settings.
variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "GCP region for regional resources."
  type        = string
}

variable "zone" {
  description = "GCP zone for zonal resources."
  type        = string
}

variable "network" {
  description = "VPC network name."
  type        = string
  default     = "default"
}

variable "subnetwork" {
  description = "Subnetwork self-link or name. Use default for default VPC subnet."
  type        = string
  default     = "default"
}

variable "vm_name" {
  description = "Backend VM instance name."
  type        = string
  default     = "quaero-backend"
}

variable "machine_type" {
  description = "Compute machine type."
  type        = string
  default     = "e2-micro"
}

variable "vm_boot_disk_size_gb" {
  description = "Boot disk size in GB."
  type        = number
  default     = 10
}

variable "vm_image" {
  description = "Boot image for the VM."
  type        = string
  default     = "projects/debian-cloud/global/images/family/debian-12"
}

variable "vm_network_tag" {
  description = "Network tag applied to backend VM."
  type        = string
  default     = "quaero-backend"
}

variable "static_ip_name" {
  description = "Reserved static external IP name."
  type        = string
  default     = "quaero-backend-ip"
}

variable "bucket_name" {
  description = "GCS bucket for uploaded PDFs."
  type        = string
}

variable "ssh_user" {
  description = "Linux SSH username provisioned on the VM."
  type        = string
  default     = "odys"
}

variable "ssh_public_keys" {
  description = "List of authorized public keys for ssh_user."
  type        = list(string)
}

variable "ssh_source_ranges" {
  description = "Source CIDRs allowed for SSH ingress."
  type        = list(string)

  validation {
    condition     = length(var.ssh_source_ranges) > 0
    error_message = "ssh_source_ranges must contain at least one CIDR."
  }
}

variable "allow_insecure_ssh_from_anywhere" {
  description = "Temporary rollout exception to allow ssh_source_ranges to include 0.0.0.0/0."
  type        = bool
  default     = false
}

variable "api_domain" {
  description = "Public API domain for NGINX server_name and cert issuance."
  type        = string
  default     = "api.quaero.odysian.dev"
}

variable "frontend_url" {
  description = "Frontend origin written into backend.env stub."
  type        = string
  default     = "https://quaero.odysian.dev"
}

variable "backend_port" {
  description = "Backend container port used by NGINX upstream and env stub."
  type        = number
  default     = 8000
}

variable "certbot_email" {
  description = "Email used for Let's Encrypt registration. Leave empty to skip cert provisioning."
  type        = string
  default     = ""
}

variable "enable_tls_bootstrap" {
  description = "Whether startup bootstrap should attempt Certbot certificate provisioning."
  type        = bool
  default     = false
}


variable "vm_service_account_scopes" {
  description = "Additional OAuth scopes attached to the VM service account. Required storage/logging/monitoring scopes are always enforced additively."
  type        = list(string)
  default     = ["https://www.googleapis.com/auth/devstorage.read_write"]
}

variable "enable_secure_boot" {
  description = "Whether to enable Shielded VM secure boot."
  type        = bool
  default     = true
}

variable "github_runner_pat" {
  description = "GitHub PAT used at startup to register the self-hosted Actions runner. Requires repository Administration write permission. Leave empty to skip runner setup."
  type        = string
  sensitive   = true
  default     = ""
}

variable "github_runner_version" {
  description = "Pinned GitHub Actions runner version (semver, no 'v' prefix). Must match an available release on github.com/actions/runner/releases."
  type        = string
  default     = "2.323.0"

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.github_runner_version))
    error_message = "github_runner_version must be a pinned semver string like '2.323.0'."
  }
}

variable "github_repository" {
  description = "GitHub repository allowed to use OIDC for Terraform ops (owner/repo)."
  type        = string
  default     = "odysian/vector-doc-qa"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must be in owner/repo format."
  }
}

variable "github_oidc_pool_id" {
  description = "Workload Identity Pool ID for GitHub Actions OIDC auth."
  type        = string
  default     = "github-actions-pool"
}

variable "github_oidc_provider_id" {
  description = "Workload Identity Pool Provider ID for GitHub Actions OIDC auth."
  type        = string
  default     = "github-actions-provider"
}

variable "terraform_ops_service_account_email" {
  description = "Service account email used by Terraform ops workflow. Leave empty to default to quaero-terraform-ops-sa@<project_id>.iam.gserviceaccount.com."
  type        = string
  default     = ""

  validation {
    condition = (
      trimspace(var.terraform_ops_service_account_email) == ""
      || can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", trimspace(var.terraform_ops_service_account_email)))
    )
    error_message = "terraform_ops_service_account_email must be empty or a valid email."
  }
}
