variable "suffix" {
  type = string

  validation {
    condition     = can(regex("^[a-z0-9]{6}$", var.suffix))
    error_message = "suffix must be 6 lowercase letters or digits."
  }
}

variable "cluster_region" {
  type    = string
  default = "koreacentral"
}

variable "storage_region" {
  type    = string
  default = "japanwest"
}

variable "budget_amount" {
  type    = number
  default = 25
}

variable "budget_email" {
  type = string
}

variable "budget_start" {
  type    = string
  default = "2026-10-01T00:00:00Z"
}

variable "vault_locked" {
  type    = bool
  default = false
}
