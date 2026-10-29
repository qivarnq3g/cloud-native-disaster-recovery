locals {
  replication_targets = {
    copy    = "image_copy"
    standby = "image_standby"
  }
}

resource "azurerm_storage_object_replication" "images" {
  for_each                       = local.replication_targets
  source_storage_account_id      = azurerm_storage_account.this["image_primary"].id
  destination_storage_account_id = azurerm_storage_account.this[each.value].id

  rules {
    source_container_name      = azurerm_storage_container.this["image_primary/images"].name
    destination_container_name = azurerm_storage_container.this["${each.value}/images"].name
    copy_blobs_created_after   = "Everything"
  }
}
