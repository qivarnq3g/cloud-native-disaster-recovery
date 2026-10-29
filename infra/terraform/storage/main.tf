locals {
  accounts = {
    backup = {
      name       = "drbackup${var.suffix}"
      group      = data.azurerm_resource_group.backup.name
      location   = var.storage_region
      containers = ["cnpg", "velero", "status"]
      versioned  = false
      change     = false
    }
    image_copy = {
      name       = "drimgcopy${var.suffix}"
      group      = data.azurerm_resource_group.backup.name
      location   = var.storage_region
      containers = ["images"]
      versioned  = true
      change     = false
    }
    vault = {
      name       = "drvault${var.suffix}"
      group      = data.azurerm_resource_group.backup.name
      location   = var.storage_region
      containers = ["vault"]
      versioned  = false
      change     = false
    }
    image_primary = {
      name       = "drimgpri${var.suffix}"
      group      = azurerm_resource_group.cluster["primary"].name
      location   = var.cluster_region
      containers = ["images"]
      versioned  = true
      change     = true
    }
    image_standby = {
      name       = "drimgstb${var.suffix}"
      group      = azurerm_resource_group.cluster["standby"].name
      location   = var.cluster_region
      containers = ["images"]
      versioned  = true
      change     = true
    }
  }

  containers = merge([
    for key, account in local.accounts : {
      for container in account.containers : "${key}/${container}" => {
        account   = key
        container = container
      }
    }
  ]...)

  dr_groups = ["rg-dr-primary", "rg-dr-standby", "rg-dr-backup"]
}

data "azurerm_client_config" "current" {}

data "azurerm_resource_group" "backup" {
  name = "rg-dr-backup"
}

resource "azurerm_resource_group" "cluster" {
  for_each = toset(["primary", "standby"])
  name     = "rg-dr-${each.key}"
  location = var.cluster_region
}

resource "azurerm_storage_account" "this" {
  for_each                        = local.accounts
  name                            = each.value.name
  resource_group_name             = each.value.group
  location                        = each.value.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = true

  blob_properties {
    versioning_enabled  = each.value.versioned
    change_feed_enabled = each.value.change

    delete_retention_policy {
      days = 7
    }
  }
}

resource "azurerm_storage_container" "this" {
  for_each              = local.containers
  name                  = each.value.container
  storage_account_id    = azurerm_storage_account.this[each.value.account].id
  container_access_type = "private"
}

resource "azurerm_storage_management_policy" "image_copy" {
  storage_account_id = azurerm_storage_account.this["image_copy"].id

  rule {
    name    = "expire-old-versions"
    enabled = true

    filters {
      blob_types = ["blockBlob"]
    }

    actions {
      version {
        delete_after_days_since_creation = 7
      }
    }
  }
}

resource "azurerm_storage_container_immutability_policy" "vault" {
  storage_container_resource_manager_id = azurerm_storage_container.this["vault/vault"].id
  immutability_period_in_days           = 7
  locked                                = var.vault_locked
  protected_append_writes_enabled       = false
}

resource "azurerm_consumption_budget_subscription" "dr" {
  name            = "dr-budget"
  subscription_id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  amount          = var.budget_amount
  time_grain      = "Monthly"

  time_period {
    start_date = var.budget_start
  }

  filter {
    dimension {
      name   = "ResourceGroupName"
      values = local.dr_groups
    }
  }

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThan"
      threshold_type = "Actual"
      contact_emails = [var.budget_email]
    }
  }
}
