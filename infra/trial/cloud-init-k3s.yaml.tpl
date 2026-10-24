#cloud-config
package_update: false
runcmd:
  - curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.37.1+k3s1" INSTALL_K3S_EXEC="server --write-kubeconfig-mode=600 --tls-san=__FQDN__" sh -
