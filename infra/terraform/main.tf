# Production backend infra composition for Quaero.
# Boundaries: provisions network/storage/VM/IAM and renders startup + Ops Agent config templates.
# Contract: required storage/logging/monitoring scopes are always enforced for the VM service account.
locals {
  vm_service_account_id = replace("${var.vm_name}-sa", "_", "-")
  ssh_keys_metadata     = join("\n", [for key in var.ssh_public_keys : "${var.ssh_user}:${key}"])
  vm_required_scopes = [
    "https://www.googleapis.com/auth/devstorage.read_write",
    "https://www.googleapis.com/auth/logging.write",
    "https://www.googleapis.com/auth/monitoring.write",
  ]
  # Keep minimum runtime scopes even when callers pass a custom scope list.
  vm_service_account_scopes = distinct(concat(var.vm_service_account_scopes, local.vm_required_scopes))
  ops_agent_config = templatefile("${path.module}/scripts/ops-agent-config.yaml.tftpl", {
    ops_agent_collect_docker_logs  = var.ops_agent_collect_docker_logs
    ops_agent_collect_host_metrics = var.ops_agent_collect_host_metrics
  })
}

resource "google_compute_address" "backend" {
  name   = var.static_ip_name
  region = var.region
}

resource "google_service_account" "backend_vm" {
  account_id   = substr(local.vm_service_account_id, 0, 30)
  display_name = "Quaero Backend VM Service Account"
}

resource "google_storage_bucket" "documents" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
}

resource "google_storage_bucket_iam_member" "backend_vm_bucket_access" {
  bucket = google_storage_bucket.documents.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.backend_vm.email}"
}

resource "google_project_iam_member" "backend_vm_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.backend_vm.email}"
}

resource "google_project_iam_member" "backend_vm_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.backend_vm.email}"
}

resource "google_compute_firewall" "allow_http" {
  name    = "quaero-allow-http"
  network = var.network

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.vm_network_tag]
}

resource "google_compute_firewall" "allow_https" {
  name    = "quaero-allow-https"
  network = var.network

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.vm_network_tag]
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "quaero-allow-ssh"
  network = var.network

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.ssh_source_ranges
  target_tags   = [var.vm_network_tag]

  lifecycle {
    precondition {
      # World-open SSH stays blocked unless an explicit temporary override is provided.
      condition = (
        var.allow_insecure_ssh_from_anywhere
        || !contains(var.ssh_source_ranges, "0.0.0.0/0")
      )
      error_message = "0.0.0.0/0 is blocked by default. Set allow_insecure_ssh_from_anywhere=true only as a temporary rollout exception."
    }
  }
}

resource "google_compute_instance" "backend" {
  name         = var.vm_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [var.vm_network_tag]

  boot_disk {
    auto_delete = true

    initialize_params {
      image = var.vm_image
      size  = var.vm_boot_disk_size_gb
    }
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork

    access_config {
      nat_ip = google_compute_address.backend.address
    }
  }

  # Restrict SSH keys to the Terraform-managed list instead of project-wide metadata keys.
  metadata = {
    "ssh-keys"               = local.ssh_keys_metadata
    "block-project-ssh-keys" = "true"
  }

  metadata_startup_script = templatefile("${path.module}/scripts/startup.sh.tftpl", {
    ssh_user             = var.ssh_user
    api_domain           = var.api_domain
    frontend_url         = var.frontend_url
    backend_port         = var.backend_port
    certbot_email        = var.certbot_email
    enable_tls_bootstrap = var.enable_tls_bootstrap
    bucket_name          = var.bucket_name
    project_id           = var.project_id
    enable_ops_agent     = var.enable_ops_agent
    ops_agent_version    = trimspace(var.ops_agent_version)
    ops_agent_config_b64 = base64encode(local.ops_agent_config)
  })

  service_account {
    email  = google_service_account.backend_vm.email
    scopes = local.vm_service_account_scopes
  }

  shielded_instance_config {
    enable_secure_boot          = var.enable_secure_boot
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  allow_stopping_for_update = true
}
