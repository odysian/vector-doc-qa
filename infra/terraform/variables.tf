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
  default     = ["0.0.0.0/0"]
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
