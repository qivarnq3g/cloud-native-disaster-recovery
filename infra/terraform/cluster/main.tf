locals {
  group      = "rg-dr-${var.cluster}"
  name       = "vm-dr-${var.cluster}"
  dns_label  = "dr-${var.cluster}-${var.suffix}"
  octet      = var.cluster == "primary" ? 10 : 20
  fqdn       = "${local.dns_label}.${var.cluster_region}.cloudapp.azure.com"
  admin_rule = { name = "admin", priority = 100, ports = ["22", "6443"] }
  web_rule   = { name = "web", priority = 110, ports = ["80", "443"] }
}

data "azurerm_resource_group" "cluster" {
  name = local.group
}

resource "azurerm_virtual_network" "k3s" {
  name                = "${local.name}-vnet"
  resource_group_name = data.azurerm_resource_group.cluster.name
  location            = var.cluster_region
  address_space       = ["10.${local.octet}.0.0/16"]
}

resource "azurerm_subnet" "k3s" {
  name                 = "default"
  resource_group_name  = data.azurerm_resource_group.cluster.name
  virtual_network_name = azurerm_virtual_network.k3s.name
  address_prefixes     = ["10.${local.octet}.0.0/24"]
}

resource "azurerm_public_ip" "k3s" {
  name                = "${local.name}-ip"
  resource_group_name = data.azurerm_resource_group.cluster.name
  location            = var.cluster_region
  sku                 = "Standard"
  allocation_method   = "Static"
  domain_name_label   = local.dns_label
}

resource "azurerm_network_security_group" "k3s" {
  name                = "${local.name}-nsg"
  resource_group_name = data.azurerm_resource_group.cluster.name
  location            = var.cluster_region

  security_rule {
    name                       = local.admin_rule.name
    priority                   = local.admin_rule.priority
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = local.admin_rule.ports
    source_address_prefixes    = var.admin_cidrs
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = local.web_rule.name
    priority                   = local.web_rule.priority
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = local.web_rule.ports
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface" "k3s" {
  name                = "${local.name}-nic"
  resource_group_name = data.azurerm_resource_group.cluster.name
  location            = var.cluster_region

  ip_configuration {
    name                          = "primary"
    subnet_id                     = azurerm_subnet.k3s.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.k3s.id
  }
}

resource "azurerm_network_interface_security_group_association" "k3s" {
  network_interface_id      = azurerm_network_interface.k3s.id
  network_security_group_id = azurerm_network_security_group.k3s.id
}

resource "azurerm_linux_virtual_machine" "k3s" {
  name                            = local.name
  resource_group_name             = data.azurerm_resource_group.cluster.name
  location                        = var.cluster_region
  size                            = var.vm_size
  admin_username                  = "dr"
  disable_password_authentication = true
  network_interface_ids           = [azurerm_network_interface.k3s.id]

  custom_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {
    k3s_version = var.k3s_version
    fqdn        = local.fqdn
    public_ip   = azurerm_public_ip.k3s.ip_address
  }))

  admin_ssh_key {
    username   = "dr"
    public_key = var.ssh_public_key
  }

  os_disk {
    name                 = "${local.name}-os"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = 32
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}

resource "azurerm_dev_test_global_vm_shutdown_schedule" "k3s" {
  virtual_machine_id    = azurerm_linux_virtual_machine.k3s.id
  location              = var.cluster_region
  enabled               = true
  daily_recurrence_time = var.auto_shutdown_time
  timezone              = var.auto_shutdown_timezone

  notification_settings {
    enabled = false
  }
}
