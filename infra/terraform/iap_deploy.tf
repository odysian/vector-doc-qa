# IAP TCP tunnel + OS Login resources for the GitHub Actions deploy workflow.
# Keeps deploy identity separate from terraform-ops-sa (separation of duties).
# GitHub Actions impersonates quaero-github-deploy-sa via the same WIF pool/provider
# that already exists for Terraform ops, so no new pool/provider setup is needed.

resource "google_project_service" "iap" {
  project = var.project_id
  service = "iap.googleapis.com"
  # Retain the API on destroy so existing IAP-protected resources stay accessible.
  disable_on_destroy = false
}

resource "google_service_account" "github_deploy" {
  account_id   = "quaero-github-deploy-sa"
  display_name = "Quaero GitHub Deploy Service Account"
  description  = "Impersonated by GitHub Actions deploy workflow via WIF; tunnels to VM through IAP with OS Login."
}

# Allow deploy SA to open IAP TCP tunnels to VM instances in this project.
resource "google_project_iam_member" "github_deploy_iap_tunnel" {
  project = var.project_id
  role    = "roles/iap.tunnelResourceAccessor"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

# Allow deploy SA to log in via OS Login (no static SSH key required).
# Using osAdminLogin so the deploy SA can run privileged commands (docker) on the VM.
resource "google_project_iam_member" "github_deploy_os_login" {
  project = var.project_id
  role    = "roles/compute.osAdminLogin"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

# Allow the GitHub Actions OIDC principal set to impersonate the deploy SA.
# Uses the same WIF pool/provider and local already defined in github_actions_oidc.tf.
resource "google_service_account_iam_member" "github_deploy_wif_user" {
  service_account_id = google_service_account.github_deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_actions_principal_set
}
