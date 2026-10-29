mock_provider "azurerm" {
  override_during = plan

  mock_data "azurerm_resource_group" {
    defaults = {
      id       = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-dr-primary"
      location = "koreacentral"
    }
  }

  mock_resource "azurerm_public_ip" {
    defaults = {
      ip_address = "20.0.0.1"
      id         = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-dr-primary/providers/Microsoft.Network/publicIPAddresses/ip"
    }
  }

  mock_resource "azurerm_virtual_network" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-dr-primary/providers/Microsoft.Network/virtualNetworks/v"
    }
  }

  mock_resource "azurerm_subnet" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-dr-primary/providers/Microsoft.Network/virtualNetworks/v/subnets/default"
    }
  }

  mock_resource "azurerm_network_interface" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-dr-primary/providers/Microsoft.Network/networkInterfaces/nic"
    }
  }

  mock_resource "azurerm_network_security_group" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-dr-primary/providers/Microsoft.Network/networkSecurityGroups/nsg"
    }
  }

  mock_resource "azurerm_linux_virtual_machine" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-dr-primary/providers/Microsoft.Compute/virtualMachines/vm-dr-primary"
    }
  }
}

variables {
  cluster        = "primary"
  suffix         = "abc123"
  admin_cidrs    = ["1.2.3.4/32"]
  ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFfwb5NKQk3doAuZkOpbXlVuRYIgBWJq0T5+XhcMJkLb test"
}

run "rejects_unknown_cluster" {
  command = plan

  variables {
    cluster = "backup"
  }

  expect_failures = [var.cluster]
}

run "primary_defaults" {
  command = plan

  assert {
    condition     = azurerm_linux_virtual_machine.k3s.size == "Standard_B2als_v2"
    error_message = "default size must be Standard_B2als_v2"
  }

  assert {
    condition     = azurerm_linux_virtual_machine.k3s.os_disk[0].disk_size_gb == 32 && azurerm_linux_virtual_machine.k3s.os_disk[0].storage_account_type == "Premium_LRS"
    error_message = "os disk must be 32 GB Premium_LRS"
  }

  assert {
    condition     = azurerm_linux_virtual_machine.k3s.disable_password_authentication
    error_message = "password login must be off"
  }

  assert {
    condition     = azurerm_linux_virtual_machine.k3s.resource_group_name == "rg-dr-primary"
    error_message = "primary vm must live in rg-dr-primary"
  }
}

run "admin_ports_only_from_admin_cidrs" {
  command = plan

  assert {
    condition = alltrue([
      for r in azurerm_network_security_group.k3s.security_rule :
      r.source_address_prefixes == toset(["1.2.3.4/32"]) if contains(r.destination_port_ranges, "22") || contains(r.destination_port_ranges, "6443")
    ])
    error_message = "ssh and kubernetes api must only accept admin cidrs"
  }

  assert {
    condition = alltrue([
      for r in azurerm_network_security_group.k3s.security_rule :
      r.source_address_prefix == "Internet" if contains(r.destination_port_ranges, "80") || contains(r.destination_port_ranges, "443")
    ])
    error_message = "web ports must accept the internet"
  }
}

run "auto_shutdown_at_23" {
  command = plan

  assert {
    condition     = azurerm_dev_test_global_vm_shutdown_schedule.k3s.daily_recurrence_time == "2300"
    error_message = "vm must shut down at 23:00"
  }

  assert {
    condition     = azurerm_dev_test_global_vm_shutdown_schedule.k3s.timezone == "SE Asia Standard Time" && azurerm_dev_test_global_vm_shutdown_schedule.k3s.enabled
    error_message = "shutdown schedule must be enabled in Vietnam time"
  }
}

run "cloud_init_pins_k3s" {
  command = plan

  assert {
    condition     = strcontains(base64decode(azurerm_linux_virtual_machine.k3s.custom_data), "v1.37.1+k3s1")
    error_message = "cloud-init must pin the k3s version"
  }
}
