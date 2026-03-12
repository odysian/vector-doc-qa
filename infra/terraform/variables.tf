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

variable "enable_ops_agent" {
  description = "Whether startup bootstrap should install/configure Google Cloud Ops Agent."
  type        = bool
  default     = false
}

variable "ops_agent_version" {
  description = "Pinned Ops Agent version. Accepts either exact apt package version or upstream X.Y.Z pin resolved to distro-qualified apt build."
  type        = string

  validation {
    condition = (
      length(trimspace(var.ops_agent_version)) > 0
      && lower(trimspace(var.ops_agent_version)) != "latest"
      && can(regex("^[0-9A-Za-z.+:~_-]+$", trimspace(var.ops_agent_version)))
    )
    error_message = "ops_agent_version must be a non-empty pinned package version and cannot be 'latest'."
  }
}

variable "ops_agent_collect_docker_logs" {
  description = "Whether Ops Agent logging config should collect Docker container logs."
  type        = bool
  default     = true
}

variable "ops_agent_collect_host_metrics" {
  description = "Whether Ops Agent metrics config should collect host metrics."
  type        = bool
  default     = true
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

variable "github_repository" {
  description = "GitHub repository allowed to use OIDC for golden image builds (owner/repo)."
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

variable "golden_image_builder_service_account_id" {
  description = "Service account ID used by GitHub Actions to build golden images."
  type        = string
  default     = "quaero-golden-build-sa"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.golden_image_builder_service_account_id))
    error_message = "golden_image_builder_service_account_id must be 6-30 chars, lowercase alnum/hyphen, and start with a letter."
  }
}

variable "golden_image_family" {
  description = "Image family used by the golden image build workflow."
  type        = string
  default     = "quaero-backend-golden"
}

variable "golden_image_retention_count" {
  description = "How many latest golden images to keep in the family for rollback."
  type        = number
  default     = 5

  validation {
    condition     = var.golden_image_retention_count >= 2
    error_message = "golden_image_retention_count must be at least 2 to preserve rollback candidates."
  }
}
