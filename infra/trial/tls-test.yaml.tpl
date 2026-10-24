apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: le-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: qivarnq3g@gmail.com
    privateKeySecretRef:
      name: le-staging-key
    solvers:
      - http01:
          ingress:
            ingressClassName: traefik
---
apiVersion: v1
kind: Namespace
metadata:
  name: tls-test
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: whoami
  namespace: tls-test
spec:
  replicas: 1
  selector:
    matchLabels: { app: whoami }
  template:
    metadata:
      labels: { app: whoami }
    spec:
      containers:
        - name: whoami
          image: traefik/whoami:v1.11
          ports: [{ containerPort: 80 }]
---
apiVersion: v1
kind: Service
metadata:
  name: whoami
  namespace: tls-test
spec:
  selector: { app: whoami }
  ports: [{ port: 80, targetPort: 80 }]
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: whoami
  namespace: tls-test
  annotations:
    cert-manager.io/cluster-issuer: le-staging
spec:
  ingressClassName: traefik
  tls:
    - hosts: [__HOST__]
      secretName: whoami-tls
  rules:
    - host: __HOST__
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service: { name: whoami, port: { number: 80 } }
