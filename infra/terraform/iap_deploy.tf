# IAP TCP tunnel resources for the GitHub Actions deploy workflow.
# Keeps deploy identity separate from terraform-ops-sa (separation of duties).
# GitHub Actions impersonates quaero-github-deploy-sa via the same WIF pool/provider
# that already exists for Terraform ops, so no new pool/provider setup is needed.
#
# Auth model: gcloud uses ephemeral key injection (metadata-based SSH) to connect as the
# existing `odys` VM user via the IAP tunnel. OS Login is intentionally NOT used because
# the deploy script calls `docker` directly (no sudo prefix), and an OS Login SA user
# (sa_<uid>) would not have docker group membership. The `odys` user already does.

resource "google_project_service" "iap" {
  project = var.project_id
  service = "iap.googleapis.com"
  # Retain the API on destroy so existing IAP-protected resources stay accessible.
  disable_on_destroy = false
}

resource "google_service_account" "github_deploy" {
  account_id   = "quaero-github-deploy-sa"
  display_name = "Quaero GitHub Deploy Service Account"
  description  = "Impersonated by GitHub Actions deploy workflow via WIF; tunnels to VM through IAP using ephemeral key injection."
}

# Allow deploy SA to open IAP TCP tunnels to VM instances in this project.
resource "google_project_iam_member" "github_deploy_iap_tunnel" {
  project = var.project_id
  role    = "roles/iap.tunnelResourceAccessor"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

# Allow deploy SA to inject a temporary SSH key into the VM's instance metadata.
# Scoped to the specific VM instance to minimize blast radius.
resource "google_compute_instance_iam_member" "github_deploy_instance_admin" {
  instance_name = var.vm_name
  zone          = var.zone
  role          = "roles/compute.instanceAdmin.v1"
  member        = "serviceAccount:${google_service_account.github_deploy.email}"
}

# gcloud compute ssh calls projects.get at the project level before key injection.
# compute.instanceAdmin.v1 scoped to the instance does not include this project-level
# read permission, so we add the read-only compute.viewer role at project scope.
resource "google_project_iam_member" "github_deploy_compute_viewer" {
  project = var.project_id
  role    = "roles/compute.viewer"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

# Allow the GitHub Actions OIDC principal set to impersonate the deploy SA.
# Uses the same WIF pool/provider and local already defined in github_actions_oidc.tf.
resource "google_service_account_iam_member" "github_deploy_wif_user" {
  service_account_id = google_service_account.github_deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_actions_principal_set
}
