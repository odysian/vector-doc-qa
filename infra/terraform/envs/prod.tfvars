project_id = "portfolio-488721"
region     = "us-east1"
zone       = "us-east1-b"

network        = "default"
subnetwork     = "default"
vm_name        = "quaero-backend"
machine_type   = "e2-micro"
static_ip_name = "quaero-backend-ip"

bucket_name          = "quaero-pdf-storage"
ssh_user             = "odys"
api_domain           = "api.quaero.odysian.dev"
frontend_url         = "https://quaero.odysian.dev"
backend_port         = 8000
enable_tls_bootstrap = true
certbot_email        = "colosimocj3@gmail.com"

ssh_public_keys = [
  "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINClsRqrZj0g8db/gn/vreWAQ+s2M3RmHdLw1XLRtkIZ odys-personal",
  "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIO/w6hxUASxsBdtAYf+SDTKJjf2J1Op8L2A/wzpERLyh gha-deploy",
]

# Tighten this to your fixed office/home IP CIDR when possible.
ssh_source_ranges = ["0.0.0.0/0"]
