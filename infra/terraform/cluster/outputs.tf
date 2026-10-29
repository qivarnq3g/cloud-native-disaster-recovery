output "public_ip" {
  value = azurerm_public_ip.k3s.ip_address
}

output "fqdn" {
  value = azurerm_public_ip.k3s.fqdn
}

output "vm_name" {
  value = azurerm_linux_virtual_machine.k3s.name
}

output "resource_group" {
  value = data.azurerm_resource_group.cluster.name
}
