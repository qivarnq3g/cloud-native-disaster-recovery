kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
  - |
    [plugins."io.containerd.grpc.v1.cri"]
      restrict_oom_score_adj = true
nodes:
  - role: control-plane
    image: kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5
    kubeadmConfigPatches:
      - |
        kind: KubeletConfiguration
        failCgroupV1: false
    extraPortMappings:
      - containerPort: 30080
        hostPort: __HOST_PORT__
        listenAddress: 127.0.0.1
