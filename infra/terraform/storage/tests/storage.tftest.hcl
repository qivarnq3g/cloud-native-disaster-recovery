mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      subscription_id = "00000000-0000-0000-0000-000000000000"
    }
  }

  mock_data "azurerm_resource_group" {
    defaults = {
      id       = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-dr-backup"
      location = "japanwest"
    }
  }
}

variables {
  suffix       = "abc123"
  budget_email = "x@example.com"
}

run "vault_is_worm_7_days" {
  command = plan

  assert {
    condition     = azurerm_storage_container_immutability_policy.vault.immutability_period_in_days == 7
    error_message = "vault must keep blobs for 7 days"
  }

  assert {
    condition     = azurerm_storage_container_immutability_policy.vault.locked == false
    error_message = "vault policy must start unlocked"
  }
}

run "image_accounts_versioned" {
  command = plan

  assert {
    condition = alltrue([
      for k in ["image_primary", "image_standby", "image_copy"] :
      azurerm_storage_account.this[k].blob_properties[0].versioning_enabled
    ])
    error_message = "image accounts must keep versions"
  }

  assert {
    condition     = azurerm_storage_account.this["backup"].blob_properties[0].versioning_enabled == false
    error_message = "backup account must not keep versions"
  }
}

run "replication_two_destinations" {
  command = plan

  assert {
    condition     = length(azurerm_storage_object_replication.images) == 2
    error_message = "images must replicate to two destinations"
  }
}

run "names_fit_storage_rules" {
  command = plan

  assert {
    condition     = alltrue([for a in azurerm_storage_account.this : can(regex("^[a-z0-9]{3,24}$", a.name))])
    error_message = "storage account names must be 3-24 lowercase letters or digits"
  }
}

run "budget_alerts" {
  command = plan

  assert {
    condition     = toset([for n in azurerm_consumption_budget_subscription.dr.notification : n.threshold]) == toset([50, 80, 100])
    error_message = "budget must alert at 50, 80 and 100 percent"
  }
}
