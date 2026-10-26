# Một cụm kind một nút. up.sh thay __HOST_PORT__ bằng cổng trên máy (API qua NodePort 30080).
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
  # Máy không cho hạ oom_score_adj (một số máy ảo, sandbox) thì runc lỗi khi tạo pod;
  # tùy chọn này chỉ kẹp giá trị, trên máy thường không đổi gì.
  - |
    [plugins."io.containerd.grpc.v1.cri"]
      restrict_oom_score_adj = true
nodes:
  - role: control-plane
    image: kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5
    kubeadmConfigPatches:
      # Kubernetes 1.35 trở đi từ chối chạy trên cgroup v1; máy dùng cgroup v2 không bị ảnh hưởng.
      - |
        kind: KubeletConfiguration
        failCgroupV1: false
    extraPortMappings:
      - containerPort: 30080
        hostPort: __HOST_PORT__
        listenAddress: 127.0.0.1
