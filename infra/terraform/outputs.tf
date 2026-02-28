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

