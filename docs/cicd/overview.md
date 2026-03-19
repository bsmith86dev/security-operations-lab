# CI/CD Pipeline — blerdmh Lab
**Stack:** GitHub Actions + Tailscale + Self-hosted Gitea (N1 Mini LXC)

---

## Pipeline Overview

```
Developer pushes code
        │
        ▼
┌───────────────────────────────────────────────────┐
│              GitHub (primary remote)              │
│                                                   │
│  Every push → 01-ci.yml                          │
│  ┌─────────────────────────────────────────────┐ │
│  │ 1. Secret scan (gitleaks + detect-secrets)  │ │
│  │ 2. YAML lint (yamllint)                     │ │
│  │ 3. Ansible lint + inventory validation      │ │
│  │ 4. k8s schema validation (kubeconform)      │ │
│  │ 5. Security policy (kube-score)             │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  PR to main/develop → 02-pr-dryrun.yml           │
│  ┌─────────────────────────────────────────────┐ │
│  │ 1. Detect changed files                     │ │
│  │ 2. Tailscale connect → reach k3s API        │ │
│  │ 3. kubectl apply --dry-run=server           │ │
│  │ 4. kubectl diff (show what changes)         │ │
│  │ 5. Ansible --syntax-check                   │ │
│  │ 6. Post PR comment with results             │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  Merge to main/develop → 03-cd-deploy.yml        │
│  ┌─────────────────────────────────────────────┐ │
│  │ 1. Tailscale connect → reach k3s API        │ │
│  │ 2. Pre-deploy cluster health check          │ │
│  │ 3. Apply namespaces → secrets → manifests   │ │
│  │ 4. Wait for rollouts                        │ │
│  │ 5. Post-deploy health check                 │ │
│  │ 6. Auto-rollback on failure                 │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  Merge to main → 04-docs.yml                     │
│  ┌─────────────────────────────────────────────┐ │
│  │ 1. Build MkDocs site (Material theme)       │ │
│  │ 2. Generate diagrams from manifests         │ │
│  │ 3. Deploy to GitHub Pages                   │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  Every push to main/develop → 05-mirror-gitea    │
│  ┌─────────────────────────────────────────────┐ │
│  │ 1. Tailscale connect → reach Gitea LXC      │ │
│  │ 2. git push --all --force to Gitea          │ │
│  └─────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────┐    ┌──────────────────────┐
│  Gitea Mirror       │    │  k3s Cluster         │
│  10.0.10.50:3000    │    │  10.0.20.10:6443     │
│  N1 Mini LXC        │    │  Auto-deployed       │
└─────────────────────┘    └──────────────────────┘
```

---

## Branch Strategy

```
main ──────────────────────────────────────────── production
  ↑                                                  deploy
  │  PR (required review)
  │
develop ────────────────────────────────────────── staging
  ↑                                                  deploy
  │  PR (no review required)
  │
feature/my-change ──── CI runs ──── PR to develop
```

**Rules:**
- `main` requires PR — no direct pushes
- `develop` allows direct pushes for rapid iteration
- Both branches trigger CD on merge
- `main` deploys to production environment (GitHub Environments gate)
- `develop` deploys immediately on push

---

## GitHub Secrets Required

Set these in: GitHub repo → Settings → Secrets and variables → Actions

| Secret | Value | Used By |
|--------|-------|---------|
| `TAILSCALE_OAUTH_CLIENT_ID` | Tailscale OAuth client ID | PR dry-run, CD, Mirror |
| `TAILSCALE_OAUTH_SECRET` | Tailscale OAuth secret | PR dry-run, CD, Mirror |
| `KUBECONFIG_BASE64` | `base64 ~/.kube/blerdmh-lab-config` | PR dry-run, CD |
| `GITEA_MIRROR_TOKEN` | Gitea API token for labadmin | Mirror workflow |
| `GITLEAKS_LICENSE` | Optional — free tier works without | Secret scan |

### Generating KUBECONFIG_BASE64

```bash
# On your workstation, after Phase 6 (k3s setup)
cat ~/.kube/blerdmh-lab-config | base64 -w 0
# Copy the output → paste as KUBECONFIG_BASE64 secret
```

### Setting up Tailscale OAuth for CI

```
1. Go to tailscale.com/admin → Settings → OAuth Clients
2. Create new OAuth client
3. Scopes: devices:write
4. Tags: tag:ci-runner (must match the tags in workflow files)
5. Copy Client ID → TAILSCALE_OAUTH_CLIENT_ID
6. Copy Client Secret → TAILSCALE_OAUTH_SECRET

Then in Tailscale ACL, add:
  "tagOwners": {
    "tag:ci-runner": ["autogroup:admin"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci-runner"],
      "dst": ["10.0.20.10:6443", "10.0.10.50:3000"]
    }
  ]
```

---

## GitHub Repository Settings

### Branch Protection (Settings → Branches)

**main branch:**
```
☑ Require a pull request before merging
☑ Require status checks to pass:
    - Secret Scan
    - YAML Lint
    - Ansible Lint
    - Kubernetes Manifest Validation
    - Security Policy Check
    - kubectl Dry-Run (Live Cluster)
☑ Require branches to be up to date before merging
☑ Do not allow bypassing the above settings
```

**develop branch:**
```
☑ Require status checks to pass:
    - Secret Scan
    - YAML Lint
☐ No required reviews (free to push directly)
```

### GitHub Environments (Settings → Environments)

**production:**
```
☑ Required reviewers: your GitHub username
☑ Wait timer: 0 minutes
☑ Deployment branches: main only
```

**staging:**
```
☐ No required reviewers
☑ Deployment branches: develop only
```

---

## Gitea Setup (N1 Mini LXC)

### Create the LXC in Proxmox

```bash
# On N1 Mini PVE — create an Ubuntu 22.04 LXC
pct create 302 local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst \
  --hostname gitea \
  --memory 1024 \
  --cores 2 \
  --net0 name=eth0,bridge=vmbr0,tag=10,ip=10.0.10.50/24,gw=10.0.10.1 \
  --storage local-lvm \
  --rootfs local-lvm:20 \
  --unprivileged 1 \
  --start 1

# Set root password
pct exec 302 -- passwd root

# Add to Ansible inventory hosts.yml:
# gitea:
#   ansible_host: 10.0.10.50
```

### Provision with Ansible

```bash
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/01-baseline.yml \
  --limit gitea \
  --ask-vault-pass

ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/06-gitea.yml \
  --ask-vault-pass
```

### Create mirror repo via Gitea UI

```
1. Log into http://10.0.10.50:3000 as labadmin
2. + → New Repository → blerdmh-lab
3. Private, no auto-init
4. Settings → API → Generate token with write:repo scope
5. Copy token → GitHub secret GITEA_MIRROR_TOKEN
```

---

## Detecting Secrets Locally Before Pushing

Install the pre-commit hook so secrets are caught before they ever leave your machine:

```bash
pip install pre-commit detect-secrets

# In repo root:
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: .*-sealed\.yml|vault\.yml|\.secrets\.baseline
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
EOF

# Initialize baseline (marks any existing non-secret patterns as allowed)
detect-secrets scan \
  --exclude-files '.*-sealed\.yml' \
  --exclude-files 'vault\.yml' > .secrets.baseline

# Install hooks
pre-commit install

# Test it
pre-commit run --all-files
```

From now on, any commit containing a detected secret will be **blocked locally** before it reaches GitHub.
