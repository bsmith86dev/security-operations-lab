# blerdmh Lab — Complete Rebuild Guide
**Domain:** blerdmh.com (external) | lab.blerdmh.local (internal)
**Stack:** OPNsense · Proxmox VE · k3s · TrueNAS Scale · Wazuh · Ansible · Helm

> **Status:** Pre-build — repo and CI/CD complete. Hardware not yet touched.
> Follow phases in strict order. Each phase has a ✅ checkpoint before proceeding.

---

## Before You Touch Hardware — Complete These First

### Workstation prerequisites

Install these tools on your admin workstation (Windows WSL2 or Linux):

```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# kubeseal (Sealed Secrets CLI)
curl -sSLo kubeseal.tar.gz \
  https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.26.3/kubeseal-0.26.3-linux-amd64.tar.gz
tar xf kubeseal.tar.gz && sudo mv kubeseal /usr/local/bin/

# Ansible
pip3 install ansible ansible-lint

# Pre-commit hooks
pip3 install pre-commit detect-secrets

# SSH key for lab (if not already created)
ssh-keygen -t ed25519 -C "blerdmh-lab" -f ~/.ssh/lab_ed25519

# Vault password file
echo "your-strong-vault-password" > ~/.vault-pass
chmod 600 ~/.vault-pass
```

### Clone the repo and set up Git

```bash
git clone https://github.com/YOUR_USERNAME/blerdmh-lab.git
cd blerdmh-lab

# Install pre-commit hooks
pre-commit install

# Initialize secret baseline
detect-secrets scan \
  --exclude-files '.*-sealed\.yml' \
  --exclude-files 'vault\.yml' > .secrets.baseline

# Verify hooks work
pre-commit run --all-files
```

### Fill in vault secrets

```bash
# Edit the vault file — fill in ALL placeholder values
ansible-vault edit ansible/inventory/group_vars/all/vault.yml
# (uses ~/.vault-pass automatically via ansible.cfg)

# Values you need before starting:
#   vault_tailscale_auth_key     — from tailscale.com/admin/settings/keys
#   vault_lab_ssh_public_key     — contents of ~/.ssh/lab_ed25519.pub
#   vault_gitea_admin_password   — choose a strong password
#   vault_gitea_secret_key       — run: openssl rand -hex 32
#   vault_gitea_internal_token   — run: openssl rand -hex 32
#   vault_wazuh_api_password     — choose a strong password
#   vault_proxmox_api_token_*    — generate after Proxmox is installed
#   vault_cloudflare_*           — from Cloudflare dashboard
#   vault_nextcloud_*            — choose strong passwords
#   vault_grafana_admin_password — choose a strong password
```

### Set up GitHub secrets

In your GitHub repo → Settings → Secrets and variables → Actions:

| Secret | How to get it |
|--------|--------------|
| `TAILSCALE_OAUTH_CLIENT_ID` | tailscale.com/admin → OAuth Clients → Create |
| `TAILSCALE_OAUTH_SECRET` | Same OAuth client |
| `KUBECONFIG_BASE64` | Generate after Phase 6 (k3s up) |
| `GITEA_MIRROR_TOKEN` | Generate after Phase 9 (Gitea up) |

### Configure Tailscale ACL for CI runners

In your Tailscale admin console (tailscale.com/admin/acls), add:

```json
{
  "tagOwners": {
    "tag:ci-runner": ["autogroup:admin"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci-runner"],
      "dst": [
        "10.0.20.10:6443",
        "10.0.10.50:3000"
      ]
    }
  ]
}
```

### Set GitHub branch protection

Settings → Branches → Add rule for `main`:

```
☑ Require pull request before merging
☑ Require status checks: Secret Scan, YAML Lint, Ansible Lint,
                          Kubernetes Manifest Validation, Security Policy Check
☑ Require branches to be up to date
☑ Do not allow bypassing
```

**✅ Pre-build checkpoint:** Pre-commit blocks a test secret commit. GitHub CI passes on a push to develop. Vault file is encrypted and committed.

---

## Phase 1 — Physical Network
**Goal:** All devices get correct IPs. OPNsense enforces VLANs. Internet works on all VLANs.
**Time estimate:** 2–3 hours

### Step 1.1 — Factory reset and configure MokerLink switch

```
1. Hold reset button 10 seconds → all LEDs flash → release
2. Connect workstation directly to Port 6 (will become ACCESS VLAN 10)
3. Set workstation to static: 192.168.0.2/24, no gateway
4. Browse to 192.168.0.1 (factory default)
5. Change switch management IP → 10.0.10.2/24, gateway 10.0.10.1
6. Save — reconnect workstation to static 10.0.10.20/24, gateway 10.0.10.1
7. Browse to 10.0.10.2
```

Create VLANs (Advanced → 802.1Q VLAN → VLAN Config):
`10, 20, 30, 31, 40, 50, 60, 61, 62, 70`

Apply every port configuration exactly as documented in `switch/mokerlink-vlan-config.md`.

### Step 1.2 — Configure OPNsense

```
1. Boot OPNsense on Glovary firewall
2. Console: assign ETH0 → WAN, ETH1 → LAN
3. Set LAN IP: 10.0.10.1/24
4. Browse to https://10.0.10.1 from workstation
5. Interfaces → Other Types → VLAN → create all 10 VLANs on ETH1
6. Assign each VLAN interface and enable it
7. Firewall → Aliases → create all aliases from opnsense-firewall-rules.md
8. Firewall → Rules → apply rules per interface from opnsense-firewall-rules.md
9. Services → Unbound DNS → enable, add all host overrides
10. Services → DHCP → enable per VLAN, add static leases for known MACs
11. System → Settings → Logging → Remote → 10.0.40.10:514 (enable after Wazuh is up)
```

**✅ Checkpoint:** `ping 10.0.10.1` succeeds from workstation. Devices on different VLANs cannot ping each other (test with a laptop on guest WiFi vs MGMT). Internet works on VLAN 60.

---

## Phase 2 — Proxmox Nodes
**Goal:** AMDPVE and N1 Mini online, VLAN-aware bridge configured, cloud-init template ready.
**Time estimate:** 2–4 hours

### Step 2.1 — Install Proxmox VE on AMDPVE

```bash
# Boot from Proxmox VE 8.x USB
# Install to Samsung 990 PRO 2TB NVMe
# Management IP: 10.0.10.10/24, gateway 10.0.10.1
# Hostname: amdpve.lab.blerdmh.local

# After install — SSH in as root
ssh root@10.0.10.10

# Copy SSH key
ssh-copy-id -i ~/.ssh/lab_ed25519.pub root@10.0.10.10
```

### Step 2.2 — Install Proxmox VE on N1 Mini

```bash
# Same process — management IP: 10.0.10.11
# Hostname: n1pve.lab.blerdmh.local
ssh root@10.0.10.11
ssh-copy-id -i ~/.ssh/lab_ed25519.pub root@10.0.10.11
```

### Step 2.3 — Add Proxmox nodes to inventory and run Ansible

```bash
# Add labadmin user to both nodes first
ssh root@10.0.10.10 "useradd -m -s /bin/bash -G sudo labadmin && \
  mkdir -p /home/labadmin/.ssh && \
  echo '$(cat ~/.ssh/lab_ed25519.pub)' >> /home/labadmin/.ssh/authorized_keys && \
  chmod 700 /home/labadmin/.ssh && \
  chmod 600 /home/labadmin/.ssh/authorized_keys && \
  chown -R labadmin:labadmin /home/labadmin/.ssh"
# Repeat for N1: ssh root@10.0.10.11

# Test Ansible connectivity
ansible -i ansible/inventory/hosts.yml proxmox_nodes -m ping

# Run Proxmox configuration playbook
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/05-proxmox.yml \
  -v
```

This configures the VLAN-aware bridge, installs node exporter, disables the
subscription nag, adds the community repo, and creates the cloud-init template.

**✅ Checkpoint:** Both Proxmox UIs accessible at `https://10.0.10.10:8006` and `https://10.0.10.11:8006`. Cloud-init template VMID 9000 visible in storage.

---

## Phase 3 — TrueNAS Scale on ZimaBoard
**Goal:** NAS online, NFS exports ready for k3s on VLAN 20.
**Time estimate:** 1–2 hours

```bash
# 1. Boot TrueNAS Scale from USB, install to Crucial P310 1TB NVMe
# 2. Management IP: 10.0.10.40/24, gateway 10.0.10.1
# 3. Access UI at https://10.0.10.40

# 4. Create storage pools (TrueNAS UI → Storage → Create Pool):
#    Pool "tank"  — mirror: 16TB WD + 8TB Seagate Barracuda
#    Pool "fast"  — single: 8TB Seagate ST6000NM0115

# 5. Create datasets (Storage → tank → Add Dataset):
#    tank/media        (for Jellyfin, Radarr, Sonarr, Lidarr)
#    tank/nextcloud    (for Nextcloud data)
#    tank/backups      (for Proxmox backups and config backups)

# 6. Add VLAN 20 network interface:
#    Network → Interfaces → Add
#    IP: 10.0.20.20/24 (no gateway — routing handled by OPNsense)

# 7. Configure NFS shares (Shares → Unix (NFS)):
#    /mnt/tank/media     → Authorized networks: 10.0.20.0/24
#    /mnt/tank/nextcloud → Authorized networks: 10.0.20.0/24
#    /mnt/tank/backups   → Authorized networks: 10.0.10.0/24, 10.0.20.0/24

# 8. Enable NFS service (Services → NFS → Start)
```

**✅ Checkpoint:** From any k3s-destined VM, test: `showmount -e 10.0.20.20` shows all three exports.

---

## Phase 4 — Raspberry Pi Setup
**Goal:** Pi 4 and Pi 5 running Ubuntu 24.04 LTS, SSH accessible, static IPs set.
**Time estimate:** 30–60 minutes

```bash
# Flash Ubuntu 24.04 LTS Server to both Pi SD cards using Raspberry Pi Imager
# In Imager advanced settings:
#   Hostname: k3s-cp (Pi 4) / k3s-worker-pi5 (Pi 5)
#   Username: labadmin
#   SSH: Enable, paste ~/.ssh/lab_ed25519.pub

# Set static IPs via cloud-init or netplan after first boot:
# Pi 4 (k3s-cp):
sudo tee /etc/netplan/00-lab.yaml << 'EOF'
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: false
      addresses: [10.0.10.30/24]
      routes:
        - to: default
          via: 10.0.10.1
      nameservers:
        addresses: [10.0.10.1]
EOF
sudo netplan apply

# Pi 5 (k3s-worker-pi5):
# Same but address: 10.0.10.31/24

# Copy SSH keys
ssh-copy-id -i ~/.ssh/lab_ed25519.pub labadmin@10.0.10.30
ssh-copy-id -i ~/.ssh/lab_ed25519.pub labadmin@10.0.10.31
```

**✅ Checkpoint:** `ansible -i ansible/inventory/hosts.yml pi_devices -m ping` returns SUCCESS for both.

---

## Phase 5 — Ansible Baseline (All Hosts)
**Goal:** All hosts hardened, Wazuh agents pre-installed, SSH locked to key-only.
**Time estimate:** 20–30 minutes

```bash
# Test all hosts respond
ansible -i ansible/inventory/hosts.yml linux_hosts -m ping

# Run baseline hardening across all hosts
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/01-baseline.yml \
  -v

# Verify: password SSH is now rejected on all hosts
ssh -o PasswordAuthentication=yes -o PubkeyAuthentication=no \
  labadmin@10.0.10.30
# Expected: Permission denied (publickey)
```

The baseline playbook applies to every Linux host:
- OS updates and baseline packages
- SSH hardened (key-only, root disabled, modern ciphers only)
- fail2ban configured (5 attempts → 1 hour ban)
- auditd running with lab ruleset
- Kernel hardening via sysctl
- Wazuh agent installed and pointed at 10.0.40.10 (will connect once Wazuh is up in Phase 7)
- Logs forwarding to rsyslog → Wazuh

**✅ Checkpoint:** All hosts pass `ansible -m ping`. Password auth rejected. `fail2ban-client status sshd` shows the jail is active.

---

## Phase 6 — k3s Cluster
**Goal:** 4-node k3s cluster running with MetalLB, Traefik, Longhorn, cert-manager, Sealed Secrets.
**Time estimate:** 1–2 hours

### Step 6.1 — Create k3s worker VMs on Proxmox

```bash
# On AMDPVE — clone template for AMD worker VM
qm clone 9000 110 --name k3s-worker-amd --full
qm set 110 --cores 8 --memory 16384
qm set 110 --net0 virtio,bridge=vmbr0,tag=20
qm set 110 --ipconfig0 ip=10.0.20.12/24,gw=10.0.20.1
qm resize 110 scsi0 +195G
qm start 110

# On N1 Mini — clone template for N1 worker VM
qm clone 9000 300 --name k3s-worker-n1 --full
qm set 300 --cores 6 --memory 10240
qm set 300 --net0 virtio,bridge=vmbr0,tag=20
qm set 300 --ipconfig0 ip=10.0.20.13/24,gw=10.0.20.1
qm resize 300 scsi0 +195G
qm start 300

# Wait for VMs to boot, copy SSH keys
ssh-copy-id -i ~/.ssh/lab_ed25519.pub labadmin@10.0.20.12
ssh-copy-id -i ~/.ssh/lab_ed25519.pub labadmin@10.0.20.13

# Run baseline on new VMs
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/01-baseline.yml \
  --limit k3s-worker-amd,k3s-worker-n1
```

### Step 6.2 — Deploy k3s cluster

```bash
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/02-k3s.yml \
  -v

# Verify cluster from workstation
export KUBECONFIG=~/.kube/blerdmh-lab-config
kubectl get nodes
# Expected — all 4 nodes Ready:
# NAME               STATUS   ROLES                  AGE
# k3s-cp             Ready    control-plane,master   Xm
# k3s-worker-pi5     Ready    <none>                 Xm
# k3s-worker-amd     Ready    <none>                 Xm
# k3s-worker-n1      Ready    <none>                 Xm

kubectl get pods -A   # All kube-system pods Running

# Apply namespaces
kubectl apply -f k3s/namespaces/namespaces.yml

# Apply network policies (requires Calico/Cilium — see network-policy/network-policies.yml)
# Skip for now if using default Flannel
```

### Step 6.3 — Label nodes and deploy GPU plugin

```bash
# Label nodes for workload scheduling
kubectl label node k3s-worker-amd workload=heavy node-type=x86
kubectl label node k3s-worker-amd amd.com/gpu=present
kubectl label node k3s-worker-n1  workload=media  node-type=x86
kubectl label node k3s-worker-pi5 workload=personal node-type=arm
kubectl label node k3s-cp         node-type=arm

# Deploy AMD GPU device plugin (only runs on GPU-labeled node)
kubectl apply -f k3s/security/amd-gpu-device-plugin.yml

# Verify GPU is allocatable (requires GPU passthrough — see Phase 8)
kubectl describe node k3s-worker-amd | grep amd.com/gpu
```

### Step 6.4 — Generate KUBECONFIG_BASE64 for GitHub

```bash
# Now that k3s is up, generate the GitHub secret
cat ~/.kube/blerdmh-lab-config | base64 -w 0
# Copy output → add to GitHub as KUBECONFIG_BASE64 secret
```

**✅ Checkpoint:** `kubectl get nodes` shows 4 nodes Ready. MetalLB assigns IPs from 10.0.20.100–200. Traefik pod running. Longhorn dashboard accessible.

---

## Phase 7 — Secrets and Cloudflare Tunnel
**Goal:** All sealed secrets created. Cloudflare tunnel connected. External access working.
**Time estimate:** 1 hour

### Step 7.1 — Create Cloudflare Tunnel

```
1. Log into dash.cloudflare.com → blerdmh.com
2. Zero Trust → Networks → Tunnels → Create a tunnel
3. Name: blerdmh-lab-k3s
4. Copy the tunnel token → add to vault.yml as vault_cloudflare_tunnel_token
5. In Tunnel → Public Hostnames, add:
   nextcloud.blerdmh.com  → http://traefik.traefik.svc.cluster.local:80
   jellyfin.blerdmh.com   → http://traefik.traefik.svc.cluster.local:80
   ha.blerdmh.com         → http://traefik.traefik.svc.cluster.local:80
   grafana.blerdmh.com    → http://traefik.traefik.svc.cluster.local:80
   proxmox.blerdmh.com    → https://10.0.10.10:8006 (TLS verify: off)
```

### Step 7.2 — Create Cloudflare Access policy for Proxmox

```
Zero Trust → Access → Applications → Add application
Type: Self-hosted
Application name: Proxmox
Application domain: proxmox.blerdmh.com
Policy: Allow
  Selector: Emails → your@email.com
  (Uses one-time PIN via email — no password needed)
```

### Step 7.3 — Seal all secrets

```bash
chmod +x k3s/security/create-secrets.sh
bash k3s/security/create-secrets.sh
# Follow prompts — enter real values for each secret
# Sealed files are written to Git-safe locations
# Commit the *-sealed.yml files

git add k3s/**/*-sealed.yml k3s/ingress/*-sealed.yml
git commit -m "feat: add sealed secrets for all services"
git push
```

### Step 7.4 — Apply cert-manager and Cloudflare tunnel

```bash
# Edit cluster-issuer.yml — replace email placeholder
nano k3s/ingress/cluster-issuer.yml

# Apply cert-manager issuers
kubectl apply -f k3s/ingress/cluster-issuer.yml

# Deploy Cloudflare tunnel
kubectl apply -f k3s/ingress/cloudflare-tunnel.yml

# Verify tunnel is connected
kubectl logs -n ingress deployment/cloudflared | grep "Registered tunnel"
```

**✅ Checkpoint:** `curl -sk https://nextcloud.blerdmh.com` returns an HTTP response from your phone (external network, not on lab WiFi). Proxmox at proxmox.blerdmh.com prompts for Cloudflare Access email.

---

## Phase 8 — GPU Passthrough
**Goal:** RX 5700 XT passed through to k3s-worker-amd VM. VAAPI working inside VM.
**Time estimate:** 1–2 hours (first time can take longer)

Follow `docs/03-GPU-PASSTHROUGH.md` step by step.

Summary:
```bash
# On AMDPVE host:
# 1. Edit GRUB — add amd_iommu=on iommu=pt
# 2. Blacklist amdgpu/radeon drivers on host
# 3. Load vfio modules
# 4. Bind GPU PCI IDs to vfio-pci
# 5. Stop k3s-worker-amd VM, add hostpci0, set q35 + UEFI, restart

# Inside k3s-worker-amd VM:
# 6. Install VAAPI libraries
# 7. Verify: vainfo shows H264/HEVC decode profiles
# 8. Verify: ls /dev/dri/renderD128 exists
```

**✅ Checkpoint:** `vainfo` inside the VM shows AMD GPU profiles. `kubectl describe node k3s-worker-amd | grep amd.com/gpu` shows `1` allocatable.

---

## Phase 9 — Security Stack VMs
**Goal:** Wazuh, IDS, OpenVAS running. All agents reporting. OPNsense logs flowing.
**Time estimate:** 2–4 hours (Wazuh install downloads ~2GB)

### Create security VMs on AMDPVE

```bash
# Wazuh VM (VMID 100, VLAN 40)
qm clone 9000 100 --name wazuh-vm --full
qm set 100 --cores 8 --memory 16384
qm set 100 --net0 virtio,bridge=vmbr0,tag=40
qm set 100 --ipconfig0 ip=10.0.40.10/24,gw=10.0.40.1
qm resize 100 scsi0 +195G && qm start 100

# IDS VM (VMID 101, VLAN 40)
qm clone 9000 101 --name ids-vm --full
qm set 101 --cores 4 --memory 8192
qm set 101 --net0 virtio,bridge=vmbr0,tag=40
qm set 101 --ipconfig0 ip=10.0.40.11/24,gw=10.0.40.1
qm resize 101 scsi0 +95G && qm start 101

# OpenVAS VM (VMID 102, VLAN 40)
qm clone 9000 102 --name openvas-vm --full
qm set 102 --cores 4 --memory 8192
qm set 102 --net0 virtio,bridge=vmbr0,tag=40
qm set 102 --ipconfig0 ip=10.0.40.12/24,gw=10.0.40.1
qm resize 102 scsi0 +95G && qm start 102

# Grafana VM (VMID 103, VLAN 40)
qm clone 9000 103 --name grafana-vm --full
qm set 103 --cores 4 --memory 8192
qm set 103 --net0 virtio,bridge=vmbr0,tag=40
qm set 103 --ipconfig0 ip=10.0.40.13/24,gw=10.0.40.1
qm resize 103 scsi0 +45G && qm start 103

# Copy SSH keys to all security VMs
for ip in 10.0.40.10 10.0.40.11 10.0.40.12 10.0.40.13; do
  ssh-copy-id -i ~/.ssh/lab_ed25519.pub labadmin@$ip
done
```

### Run Ansible security playbooks

```bash
# Baseline all security VMs
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/01-baseline.yml \
  --limit security_vms

# Deploy full security stack
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/03-security.yml \
  -v
```

### Enable OPNsense syslog forwarding

```
OPNsense UI → System → Settings → Logging → Remote Logging
  Enable: ✓
  IP: 10.0.40.10
  Port: 514
  Protocol: UDP
  Facility: everything
Save
```

**✅ Checkpoint:** Wazuh dashboard loads at `https://10.0.40.10`. All k3s nodes and security VMs show as active agents. OPNsense firewall events visible in Wazuh. OpenVAS accessible at `https://10.0.40.12:9392`.

---

## Phase 10 — Personal Services (k3s Workloads)
**Goal:** Nextcloud, Jellyfin, Home Assistant, Grafana all running and externally accessible.
**Time estimate:** 30–60 minutes

```bash
# Install NFS provisioner for TrueNAS volumes
helm repo add nfs-subdir-external-provisioner \
  https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/
helm install nfs-provisioner \
  nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
  --set nfs.server=10.0.20.20 \
  --set nfs.path=/mnt/tank \
  --set storageClass.name=nfs-media

# Deploy all workloads
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/04-k3s-workloads.yml \
  -v

# Watch rollouts
kubectl rollout status deployment/nextcloud -n personal
kubectl rollout status deployment/jellyfin   -n media
kubectl rollout status deployment/homeassistant -n homeauto
kubectl rollout status deployment/grafana    -n monitoring

# Check for any problem pods
kubectl get pods -A | grep -v Running | grep -v Completed
```

### Configure Jellyfin hardware transcoding

```
1. Browse to https://jellyfin.blerdmh.com → Admin → Playback
2. Transcoding:
   Hardware acceleration: Video Acceleration API (VAAPI)
   VA-API Device: /dev/dri/renderD128
   Enable hardware decoding: H264, HEVC, VP9 ✓
3. Save and test with a 4K HEVC file → check server activity shows GPU
```

**✅ Checkpoint:** All 5 external URLs load from your phone on cellular:
- `nextcloud.blerdmh.com` — Nextcloud login
- `jellyfin.blerdmh.com` — Jellyfin media
- `ha.blerdmh.com` — Home Assistant
- `grafana.blerdmh.com` — Grafana dashboards
- `proxmox.blerdmh.com` — Cloudflare Access login

---

## Phase 11 — Gitea Mirror
**Goal:** Self-hosted Gitea running on N1 Mini LXC, receiving GitHub mirror pushes.
**Time estimate:** 30–45 minutes

### Create Gitea LXC on N1 Mini

```bash
# SSH into N1 Mini Proxmox
ssh root@10.0.10.11

# Download Ubuntu 22.04 LXC template
pveam update
pveam download local ubuntu-22.04-standard_22.04-1_amd64.tar.zst

# Create LXC container
pct create 302 local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst \
  --hostname gitea \
  --memory 1024 \
  --cores 2 \
  --net0 name=eth0,bridge=vmbr0,tag=10,ip=10.0.10.50/24,gw=10.0.10.1 \
  --storage local-lvm \
  --rootfs local-lvm:20 \
  --unprivileged 1 \
  --features nesting=1 \
  --start 1

# Set root password and create labadmin
pct exec 302 -- bash -c "
  passwd root <<< 'temp-root-pass'$'\n''temp-root-pass'
  useradd -m -s /bin/bash -G sudo labadmin
  mkdir -p /home/labadmin/.ssh
  echo '$(cat ~/.ssh/lab_ed25519.pub)' >> /home/labadmin/.ssh/authorized_keys
  chmod 700 /home/labadmin/.ssh
  chmod 600 /home/labadmin/.ssh/authorized_keys
  chown -R labadmin:labadmin /home/labadmin/.ssh
  apt update && apt install -y sudo python3
"

# Add gitea to inventory (update ansible/inventory/hosts.yml):
# Under a new 'gitea' group or standalone:
#   gitea:
#     ansible_host: 10.0.10.50
#     vm_role: gitea

# Run Ansible
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/06-gitea.yml \
  -v
```

### Generate Gitea API token for GitHub mirror

```
1. Browse to http://10.0.10.50:3000
2. Login as labadmin (vault_gitea_admin_password)
3. Settings → Applications → Generate Token
   Name: github-mirror
   Scopes: write:repository
4. Copy token → add to GitHub secrets as GITEA_MIRROR_TOKEN
```

**✅ Checkpoint:** Push a commit to develop branch → GitHub Actions `05-mirror-gitea.yml` runs → repo visible at `http://10.0.10.50:3000/labadmin/blerdmh-lab`.

---

## Phase 12 — Red/Purple Team Lab
**Goal:** Windows AD lab online. Kali configured. Ready for detection engineering exercises.
**Time estimate:** 2–3 hours

```bash
# On AMDPVE — create Windows Server 2022 VM (manual install)
# Download Windows Server 2022 Evaluation ISO from Microsoft
# Upload to Proxmox: Datacenter → amdpve → local → ISO Images → Upload

# Create AD domain controller VM
qm create 201 \
  --name win-dc01 \
  --cores 4 --memory 8192 \
  --net0 virtio,bridge=vmbr0,tag=62 \
  --ostype win11 \
  --bios ovmf \
  --machine q35 \
  --efidisk0 local-lvm:1,efitype=4m \
  --scsi0 local-lvm:100 \
  --ide2 local-lvm:cloudinit \
  --cdrom local:iso/WinServer2022.iso
qm start 201

# Create Windows 11 workstation VM (VMID 202, same process)
# Install Windows → join to domain

# Create Kali Linux VM
qm create 200 \
  --name kali-red \
  --cores 4 --memory 8192 \
  --net0 virtio,bridge=vmbr0,tag=61 \
  --ostype l26 \
  --scsi0 local-lvm:100 \
  --cdrom local:iso/kali-linux-2024.1-installer-amd64.iso
qm start 200
```

Post-install on Windows DC:
```powershell
# Install AD DS role and promote to domain controller
Install-WindowsFeature -Name AD-Domain-Services -IncludeManagementTools
Install-ADDSForest -DomainName "lab.blerdmh.local" -InstallDns

# Install Wazuh agent on DC (downloads from Wazuh manager)
# Wazuh UI → Agents → Deploy new agent → Windows → copy installer command
```

**✅ Final checkpoint:** Full lab operational.
- All 4 k3s nodes Ready
- Wazuh shows agents from: k3s nodes, security VMs, Windows DC
- All external services accessible via Cloudflare
- Tailscale provides VPN access to 10.0.10.0/24, 10.0.20.0/24, 10.0.40.0/24
- GitHub CI passes on every push
- Gitea mirror syncing on every push to main/develop
- GitHub Pages docs site live at `YOUR_USERNAME.github.io/blerdmh-lab`

---

## Day-to-Day Operations

```bash
# Check cluster health
kubectl get nodes && kubectl get pods -A | grep -v Running

# Deploy a manifest change
git add k3s/personal/nextcloud.yml
git commit -m "fix: increase nextcloud memory limit"
git push origin develop
# → CI runs → PR dry-run validates → merge to main → CD auto-deploys

# Run Ansible against specific host
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/01-baseline.yml \
  --limit wazuh-vm

# View Wazuh alerts from CLI
ssh labadmin@10.0.40.10
sudo tail -f /var/ossec/logs/alerts/alerts.json | python3 -m json.tool

# Check Suricata alerts
ssh labadmin@10.0.40.11
sudo tail -f /var/log/suricata/eve.json | jq 'select(.event_type=="alert")'

# Force Gitea mirror sync
gh workflow run 05-mirror-gitea.yml --ref main

# Rotate a sealed secret
kubectl delete secret nextcloud-secrets -n personal
bash k3s/security/create-secrets.sh   # re-runs interactively
kubectl rollout restart deployment/nextcloud -n personal
```

## Backup Strategy

```bash
# Proxmox VM backups → TrueNAS (tank/backups)
# Set up in Proxmox: Datacenter → Backup → Add
# Schedule: daily 02:00, retention: 7 days
# Storage: add TrueNAS NFS as backup storage first

# k3s persistent data → Longhorn snapshots
# Longhorn UI → Volumes → each volume → Create Snapshot

# Sealed Secrets master key — CRITICAL
kubectl get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key=active \
  -o yaml > ~/sealed-secrets-master-key-$(date +%Y%m%d).yml
# Store this offline — password manager or encrypted USB
# WITHOUT this key you cannot recover sealed secrets if the cluster is rebuilt

# Ansible vault backup
cp ansible/inventory/group_vars/all/vault.yml \
  ~/vault-backup-$(date +%Y%m%d).yml
# Store encrypted — it IS encrypted, but keep it safe
```
