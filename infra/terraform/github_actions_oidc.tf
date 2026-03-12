locals {
  github_actions_principal_set = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions.name}/attribute.repository/${var.github_repository}"
  terraform_ops_service_account_email_effective = (
    length(trimspace(var.terraform_ops_service_account_email)) > 0
    ? trimspace(var.terraform_ops_service_account_email)
    : "quaero-terraform-ops-sa@${var.project_id}.iam.gserviceaccount.com"
  )
}

resource "google_iam_workload_identity_pool" "github_actions" {
  workload_identity_pool_id = var.github_oidc_pool_id
  display_name              = "GitHub Actions Pool"
  description               = "OIDC trust pool for GitHub Actions workflows."
}

resource "google_iam_workload_identity_pool_provider" "github_actions" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions.workload_identity_pool_id
  workload_identity_pool_provider_id = var.github_oidc_provider_id
  display_name                       = "GitHub Actions Provider"
  description                        = "OIDC provider for token.actions.githubusercontent.com."

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "terraform_ops_wif_user" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.terraform_ops_service_account_email_effective}"
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_actions_principal_set
}
