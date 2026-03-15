output "vm_name" {
  description = "Backend VM instance name."
  value       = google_compute_instance.backend.name
}

output "vm_external_ip" {
  description = "Backend VM external static IP."
  value       = google_compute_address.backend.address
}

output "vm_service_account_email" {
  description = "Service account used by backend VM."
  value       = google_service_account.backend_vm.email
}

output "documents_bucket_name" {
  description = "GCS bucket used by backend for document storage."
  value       = google_storage_bucket.documents.name
}

output "github_actions_workload_identity_provider" {
  description = "Full Workload Identity Provider resource name for GitHub Actions auth."
  value       = google_iam_workload_identity_pool_provider.github_actions.name
}

output "terraform_ops_service_account_email_effective" {
  description = "Service account email bound to GitHub OIDC for Terraform ops."
  value       = local.terraform_ops_service_account_email_effective
}

output "github_deploy_service_account_email" {
  description = "Service account email for the GitHub Actions deploy workflow to impersonate via WIF."
  value       = google_service_account.github_deploy.email
}
