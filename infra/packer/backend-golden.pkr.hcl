packer {
  required_plugins {
    googlecompute = {
      source  = "github.com/hashicorp/googlecompute"
      version = ">= 1.1.7"
    }
  }
}

variable "project_id" {
  type = string
}

variable "zone" {
  type = string
}

variable "machine_type" {
  type    = string
  default = "e2-medium"
}

variable "source_image_family" {
  type    = string
  default = "debian-12"
}

variable "source_image_project_id" {
  type    = string
  default = "debian-cloud"
}

variable "image_name" {
  type = string
}

variable "image_family" {
  type = string
}

variable "build_timestamp_label" {
  type = string
}

variable "repo_label" {
  type = string
}

variable "commit_sha_short" {
  type = string
}

variable "workflow_run_id" {
  type = string
}

source "googlecompute" "backend_golden" {
  project_id              = var.project_id
  zone                    = var.zone
  machine_type            = var.machine_type
  source_image_family     = var.source_image_family
  source_image_project_id = [var.source_image_project_id]
  image_name              = var.image_name
  image_family            = var.image_family
  disk_size               = 20
  ssh_username            = "packer"
  use_os_login            = true
  image_labels = {
    quaero_build_time = var.build_timestamp_label
    quaero_commit     = var.commit_sha_short
    quaero_repo       = var.repo_label
    quaero_role       = "backend-golden"
    quaero_run_id     = var.workflow_run_id
  }
}

build {
  name    = "backend-golden-image"
  sources = ["source.googlecompute.backend_golden"]

  provisioner "shell" {
    inline = [
      "set -euxo pipefail",
      "sudo apt-get update",
      "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io nginx certbot python3-certbot-nginx ca-certificates curl",
      "curl -sS https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh -o /tmp/add-google-cloud-ops-agent-repo.sh",
      "sudo bash /tmp/add-google-cloud-ops-agent-repo.sh --also-install",
      "rm -f /tmp/add-google-cloud-ops-agent-repo.sh",
      "sudo mkdir -p /opt/quaero/deploy /opt/quaero/env /opt/quaero/logs",
      "sudo chmod 755 /opt/quaero /opt/quaero/deploy /opt/quaero/env /opt/quaero/logs",
      "sudo systemctl enable docker",
      "sudo systemctl enable nginx",
      "sudo systemctl enable certbot.timer",
      "sudo systemctl enable google-cloud-ops-agent",
      "sudo apt-get clean",
      "sudo rm -rf /var/lib/apt/lists/*",
    ]
  }
}
