# Secrets Management

This lab uses a layered secrets strategy — different tools for different contexts,
all designed so **no plaintext secret ever touches Git**.

---

## The Three Layers

```
Layer 1 — Local machine
  pre-commit hooks (gitleaks + detect-secrets)
  Catches secrets before they're even staged

Layer 2 — Ansible secrets (vault.yml)
  ansible-vault AES256 encryption
  For infrastructure provisioning (passwords, tokens, keys)

Layer 3 — Kubernetes secrets (Sealed Secrets)
  kubeseal + Bitnami Sealed Secrets controller
  For k3s workload secrets (app passwords, API keys)
```

---

## Layer 1 — Pre-commit (Local)

Install once per machine:

```bash
pip install pre-commit detect-secrets
pre-commit install

# Initialize the baseline (marks allowed patterns)
detect-secrets scan \
  --exclude-files '.*-sealed\.yml' \
  --exclude-files 'vault\.yml' \
  > .secrets.baseline

# Test it
pre-commit run --all-files
```

From now on, any commit containing a detected secret is **blocked at commit time**.
The CI pipeline (`01-ci.yml`) runs the same checks as a second gate.

---

## Layer 2 — Ansible Vault

Used for: infrastructure passwords, Tailscale auth key, Proxmox tokens, Gitea secrets.

### Workflow

```bash
# Edit secrets (decrypts temporarily in $EDITOR, re-encrypts on save)
ansible-vault edit ansible/inventory/group_vars/all/vault.yml

# View without editing
ansible-vault view ansible/inventory/group_vars/all/vault.yml

# Encrypt a new file
ansible-vault encrypt path/to/file.yml

# Use a password file so you don't type it every run
echo "your-vault-password" > ~/.vault-pass
chmod 600 ~/.vault-pass
# ansible.cfg already points to ~/.vault-pass
```

### Running playbooks with vault

```bash
# Using password file (ansible.cfg configures this automatically)
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/01-baseline.yml

# Or prompt for password
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/01-baseline.yml \
  --ask-vault-pass
```

### Reference vault variables in your roles

```yaml
# In any task or template, reference vault variables directly:
- name: Set Gitea admin password
  shell: gitea admin user create --password "{{ vault_gitea_admin_password }}"
  no_log: true   # Always add no_log: true when using vault vars in shell tasks
```

### CI/CD and vault

The GitHub Actions CI pipeline does **syntax-only** checks on Ansible — it never
decrypts vault. The vault password is never stored in GitHub secrets.
Real deployments requiring vault are run manually from your workstation.

---

## Layer 3 — Sealed Secrets (Kubernetes)

Used for: app passwords, Cloudflare API keys, Nextcloud DB passwords, Grafana admin password.

Sealed Secrets encrypt a Kubernetes Secret with the cluster's public key.
The encrypted `SealedSecret` resource is safe to commit to Git.
Only the Sealed Secrets controller running in k3s can decrypt it.

### Initial setup

```bash
# Install kubeseal on your workstation
curl -sSLo kubeseal.tar.gz \
  https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.26.3/kubeseal-0.26.3-linux-amd64.tar.gz
tar xf kubeseal.tar.gz && sudo mv kubeseal /usr/local/bin/

# Verify controller is running in cluster
kubectl get pods -n kube-system | grep sealed-secrets
```

### Creating a sealed secret

```bash
# Step 1 — Create a regular secret (dry-run, never applied to cluster)
kubectl create secret generic my-secret \
  --from-literal=password="my-super-secret-password" \
  --namespace=personal \
  --dry-run=client -o yaml > /tmp/my-secret.yml

# Step 2 — Seal it (output is safe to commit)
kubeseal --format=yaml < /tmp/my-secret.yml > k3s/personal/my-secret-sealed.yml

# Step 3 — Delete the plaintext file
rm /tmp/my-secret.yml

# Step 4 — Apply to cluster
kubectl apply -f k3s/personal/my-secret-sealed.yml

# Step 5 — Commit the sealed file
git add k3s/personal/my-secret-sealed.yml
git commit -m "feat: add sealed secret for personal/my-secret"
```

### Using the create-secrets.sh script

The `k3s/security/create-secrets.sh` script automates creation of all
lab secrets interactively:

```bash
chmod +x k3s/security/create-secrets.sh
bash k3s/security/create-secrets.sh
```

It will prompt for each secret value, seal them, and apply them to the cluster.
The plaintext values are never written to disk.

### Rotating a sealed secret

If a secret is compromised:

```bash
# 1. Delete the existing secret from cluster
kubectl delete secret my-secret -n personal

# 2. Re-run create-secrets.sh or create a new sealed secret
# 3. Apply the new sealed file
kubectl apply -f k3s/personal/my-secret-sealed.yml

# 4. Restart the affected deployment
kubectl rollout restart deployment/nextcloud -n personal
```

### Backup the Sealed Secrets private key

If you lose the Sealed Secrets controller key, you cannot decrypt your secrets.
Back it up immediately after cluster setup:

```bash
# Export the private key (KEEP THIS SAFE — treat like a root CA key)
kubectl get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key=active \
  -o yaml > ~/sealed-secrets-master-key-BACKUP.yml

# Store this in a password manager or encrypted USB — NOT in Git
```

---

## GitHub Actions Secrets

Set in: GitHub repo → Settings → Secrets and variables → Actions

| Secret | Purpose | How to get |
|--------|---------|------------|
| `TAILSCALE_OAUTH_CLIENT_ID` | CI runner Tailnet access | tailscale.com/admin → OAuth Clients |
| `TAILSCALE_OAUTH_SECRET` | CI runner Tailnet access | Same as above |
| `KUBECONFIG_BASE64` | kubectl cluster access | `base64 ~/.kube/blerdmh-lab-config` |
| `GITEA_MIRROR_TOKEN` | Push to Gitea mirror | Gitea UI → Settings → Applications |
| `GITLEAKS_LICENSE` | Optional enhanced scanning | gitleaks.io (free tier works without) |

### Generating KUBECONFIG_BASE64

```bash
# After Phase 6 (k3s setup), on your workstation:
cat ~/.kube/blerdmh-lab-config | base64 -w 0
# Copy output → paste as KUBECONFIG_BASE64 in GitHub secrets
```

---

## What Goes Where — Quick Reference

| Secret type | Tool | Committed to Git? |
|-------------|------|-------------------|
| Infrastructure passwords | ansible-vault | ✅ Yes (encrypted) |
| k3s app secrets | Sealed Secrets | ✅ Yes (sealed) |
| GitHub Actions secrets | GitHub Secrets | ❌ No (GitHub manages) |
| Sealed Secrets master key | Offline backup | ❌ Never |
| Vault password | `~/.vault-pass` | ❌ Never |
| SSH private key | `~/.ssh/lab_ed25519` | ❌ Never |
