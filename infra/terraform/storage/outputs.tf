output "backup_account" {
  value = azurerm_storage_account.this["backup"].name
}

output "image_copy_account" {
  value = azurerm_storage_account.this["image_copy"].name
}

output "vault_account" {
  value = azurerm_storage_account.this["vault"].name
}

output "image_primary_account" {
  value = azurerm_storage_account.this["image_primary"].name
}

output "image_standby_account" {
  value = azurerm_storage_account.this["image_standby"].name
}

output "resource_group_primary" {
  value = azurerm_resource_group.cluster["primary"].name
}

output "resource_group_standby" {
  value = azurerm_resource_group.cluster["standby"].name
}
