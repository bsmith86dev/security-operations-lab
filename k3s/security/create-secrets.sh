---
# k3s/security/sealed-secrets-guide.md converted to create-secrets.sh
# This script generates all required Kubernetes secrets
# Run ONCE after k3s is up, before applying any manifests
# Secrets are sealed with kubeseal and safe to commit to Git

#!/usr/bin/env bash
set -euo pipefail

# ─── Prerequisites ────────────────────────────────────────────────────────
# Install kubeseal locally:
#   wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.26.3/kubeseal-0.26.3-linux-amd64.tar.gz
#   tar xvf kubeseal*.tar.gz && mv kubeseal /usr/local/bin/

KUBECONFIG="${HOME}/.kube/blerdmh-lab-config"
export KUBECONFIG

echo "=== blerdmh Lab — Secret Generation ==="
echo "WARNING: Enter real values. These will be sealed and safe to commit."
echo ""

# ─── Cloudflare credentials ──────────────────────────────────────────────
read -p "Cloudflare account email: " CF_EMAIL
read -s -p "Cloudflare Global API Key: " CF_API_KEY
echo ""
read -p "Cloudflare Tunnel Token (from Zero Trust dashboard): " CF_TUNNEL_TOKEN
echo ""

kubectl create secret generic cloudflare-credentials \
  --from-literal=email="${CF_EMAIL}" \
  --from-literal=api-key="${CF_API_KEY}" \
  --namespace=traefik \
  --dry-run=client -o yaml | \
  kubeseal --format=yaml > k3s/ingress/cloudflare-credentials-sealed.yml

kubectl create secret generic cloudflare-tunnel \
  --from-literal=tunnel-token="${CF_TUNNEL_TOKEN}" \
  --namespace=ingress \
  --dry-run=client -o yaml | \
  kubeseal --format=yaml > k3s/ingress/cloudflare-tunnel-sealed.yml

echo "[OK] Cloudflare secrets sealed"

# ─── Tailscale auth key ──────────────────────────────────────────────────
read -s -p "Tailscale Auth Key (from tailscale.com/admin/settings/keys): " TS_KEY
echo ""

# This goes into Ansible vars (vault-encrypted), not k8s
cat > ansible/inventory/group_vars/all/vault.yml << EOF
# Encrypt this file with: ansible-vault encrypt ansible/inventory/group_vars/all/vault.yml
tailscale_auth_key: "${TS_KEY}"
EOF
echo "[OK] Tailscale key written to ansible vault file (encrypt it!)"
echo "     Run: ansible-vault encrypt ansible/inventory/group_vars/all/vault.yml"

# ─── Nextcloud secrets ───────────────────────────────────────────────────
read -s -p "Nextcloud admin password: " NC_ADMIN_PASS
echo ""
read -s -p "Nextcloud MySQL root password: " NC_MYSQL_ROOT
echo ""
read -s -p "Nextcloud MySQL user password: " NC_MYSQL_PASS
echo ""

kubectl create secret generic nextcloud-secrets \
  --from-literal=admin-password="${NC_ADMIN_PASS}" \
  --from-literal=mysql-root-password="${NC_MYSQL_ROOT}" \
  --from-literal=mysql-password="${NC_MYSQL_PASS}" \
  --namespace=personal \
  --dry-run=client -o yaml | \
  kubeseal --format=yaml > k3s/personal/nextcloud-secrets-sealed.yml

echo "[OK] Nextcloud secrets sealed"

# ─── Grafana secrets ─────────────────────────────────────────────────────
read -s -p "Grafana admin password: " GRAFANA_PASS
echo ""

kubectl create secret generic grafana-secrets \
  --from-literal=admin-password="${GRAFANA_PASS}" \
  --namespace=monitoring \
  --dry-run=client -o yaml | \
  kubeseal --format=yaml > k3s/monitoring/grafana-secrets-sealed.yml

echo "[OK] Grafana secrets sealed"

# ─── Apply all sealed secrets ─────────────────────────────────────────────
echo ""
echo "=== Applying sealed secrets to cluster ==="
kubectl apply -f k3s/ingress/cloudflare-credentials-sealed.yml
kubectl apply -f k3s/ingress/cloudflare-tunnel-sealed.yml
kubectl apply -f k3s/personal/nextcloud-secrets-sealed.yml
kubectl apply -f k3s/monitoring/grafana-secrets-sealed.yml

echo ""
echo "=== Done! ==="
echo "Sealed secret files have been written to Git-safe locations."
echo "The original plaintext values are NOT saved anywhere."
echo "Commit the *-sealed.yml files to your Git repo."
