variable "cluster" {
  type = string

  validation {
    condition     = contains(["primary", "standby"], var.cluster)
    error_message = "cluster must be primary or standby."
  }
}

variable "suffix" {
  type = string
}

variable "vm_size" {
  type    = string
  default = "Standard_B2als_v2"
}

variable "cluster_region" {
  type    = string
  default = "koreacentral"
}

variable "admin_cidrs" {
  type = list(string)
}

variable "ssh_public_key" {
  type = string
}

variable "k3s_version" {
  type    = string
  default = "v1.37.1+k3s1"
}

variable "auto_shutdown_time" {
  type    = string
  default = "2300"
}

variable "auto_shutdown_timezone" {
  type    = string
  default = "SE Asia Standard Time"
}
