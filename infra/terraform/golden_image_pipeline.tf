data "google_project" "current" {
  project_id = var.project_id
}

locals {
  github_actions_principal_set          = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions.name}/attribute.repository/${var.github_repository}"
  default_compute_service_account_email = "${data.google_project.current.number}-compute@developer.gserviceaccount.com"
  golden_image_builder_project_roles = toset([
    "roles/compute.imageAdmin",
    "roles/compute.instanceAdmin.v1",
    "roles/compute.networkUser",
  ])
}

resource "google_service_account" "golden_image_builder" {
  account_id   = var.golden_image_builder_service_account_id
  display_name = "Quaero Golden Image Builder"
}

resource "google_project_iam_member" "golden_image_builder_roles" {
  for_each = local.golden_image_builder_project_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.golden_image_builder.email}"
}

resource "google_service_account_iam_member" "golden_image_builder_default_compute_sa_user" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.default_compute_service_account_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.golden_image_builder.email}"
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

resource "google_service_account_iam_member" "golden_image_builder_wif_user" {
  service_account_id = google_service_account.golden_image_builder.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_actions_principal_set
}
