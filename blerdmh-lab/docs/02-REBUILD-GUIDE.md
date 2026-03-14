# blerdmh Lab — Complete Rebuild Guide
**Domain:** blerdmh.com | **Stack:** OPNsense + Proxmox + k3s + TrueNAS

This is your step-by-step bring-up guide. Follow phases in order.
Each phase has a clear completion checkpoint before moving to the next.

---

## Prerequisites

### On your workstation, install:
```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# kubeseal
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.26.3/kubeseal-0.26.3-linux-amd64.tar.gz
tar xvf kubeseal*.tar.gz && sudo mv kubeseal /usr/local/bin/

# Ansible
pip3 install ansible

# Generate SSH key for lab
ssh-keygen -t ed25519 -C "blerdmh-lab" -f ~/.ssh/lab_ed25519
```

### Clone this repo:
```bash
git clone https://github.com/YOUR_USERNAME/blerdmh-lab.git
cd blerdmh-lab
```

---

## Phase 1 — Physical Network (Day 1)
**Goal:** All devices get correct IPs. OPNsense enforces VLANs. Internet works.

### Step 1.1 — Configure MokerLink Switch
1. Factory reset the switch (hold reset button 10s)
2. Connect your workstation directly to port 6 (ACCESS VLAN 10)
3. Set your workstation to static IP `10.0.10.20/24`
4. Access switch UI at `192.168.0.1` (factory default)
5. Change switch management IP to `10.0.10.2`
6. Create VLANs: 10, 20, 30, 31, 40, 50, 60, 61, 62, 70
7. Configure each port per `switch/mokerlink-vlan-config.md`
8. Enable RSTP spanning tree
9. Save config

### Step 1.2 — Configure OPNsense
1. Boot OPNsense on the Glovary firewall
2. Assign ETH0 → WAN, ETH1 → LAN (becomes MGMT trunk)
3. Set LAN IP to `10.0.10.1/24`
4. Access UI at `https://10.0.10.1` from workstation
5. Create VLAN interfaces per `switch/opnsense-firewall-rules.md`
6. Create all firewall aliases
7. Apply firewall rules for each interface
8. Configure Unbound DNS with internal overrides
9. Configure DHCP with static leases for all known MACs
10. Enable syslog forwarding (will activate once Wazuh is up)

**✅ Checkpoint:** All devices get correct IPs. You can ping 10.0.10.1 from each VLAN. Inter-VLAN traffic is blocked per rules.

---

## Phase 2 — Proxmox Nodes (Day 1-2)
**Goal:** Both Proxmox nodes online, networked, cloud-init template ready.

### Step 2.1 — AMDPVE
```bash
# After Proxmox install, SSH in as root
ssh root@10.0.10.10

# Configure VLAN-aware bridge (see docs/01-PROXMOX-VM-LAYOUT.md)
nano /etc/network/interfaces
# Paste the bridge config, then:
systemctl restart networking

# Set Proxmox subscription notice bypass (community use)
sed -i.bak 's/NotFound/Active/g' /usr/share/javascript/proxmox-widget-toolkit/proxmoxlib.js

# Add Ceph repository and install
pveceph install --version reef
```

### Step 2.2 — N1 Mini
```bash
# Same bridge config, different IP
# IP: 10.0.10.11
```

### Step 2.3 — Create Cloud-Init Template
```bash
# Run on AMDPVE — creates reusable VM template
# See docs/01-PROXMOX-VM-LAYOUT.md for full commands
wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
# ... (full commands in VM layout doc)
```

**✅ Checkpoint:** Both Proxmox UIs accessible at 10.0.10.10:8006 and 10.0.10.11:8006. Cloud-init template exists as VMID 9000.

---

## Phase 3 — TrueNAS on ZimaBoard (Day 2)
**Goal:** NAS online with NFS exports ready for k3s.

```bash
# Install TrueNAS Scale on ZimaBoard
# Boot from USB, install to the 1TB Crucial NVMe
# Set management IP: 10.0.10.40/24, gateway 10.0.10.1

# After install — access UI at https://10.0.10.40
# Create pool "tank" with 16TB WD + 8TB Seagate
# Create pool "fast" with remaining NVMe space
# Create datasets per docs/01-PROXMOX-VM-LAYOUT.md
# Configure NFS exports

# Set static IP on TrueNAS VLAN 20 interface for NFS traffic: 10.0.20.20
```

**✅ Checkpoint:** NFS exports accessible from VLAN 20. Test: `mount -t nfs 10.0.20.20:/mnt/tank/media /mnt/test`

---

## Phase 4 — Raspberry Pi Setup (Day 2-3)
**Goal:** Pi 4 and Pi 5 running Ubuntu, SSH accessible, ready for Ansible.

```bash
# Flash Ubuntu 24.04 LTS to both Pi SD cards using Raspberry Pi Imager
# Enable SSH, set username: labadmin
# Configure static IPs in /etc/netplan:

# Pi 4 (k3s-cp): 10.0.10.30/24 gw 10.0.10.1
# Pi 5 (k3s-worker): 10.0.10.31/24 gw 10.0.10.1

# Copy SSH key to both:
ssh-copy-id -i ~/.ssh/lab_ed25519.pub labadmin@10.0.10.30
ssh-copy-id -i ~/.ssh/lab_ed25519.pub labadmin@10.0.10.31
```

**✅ Checkpoint:** `ansible -i ansible/inventory/hosts.yml pi_devices -m ping` returns SUCCESS.

---

## Phase 5 — Ansible Baseline (Day 3)
**Goal:** All hosts hardened, Wazuh agents pre-installed, SSH locked down.

```bash
cd blerdmh-lab

# Encrypt Tailscale key
ansible-vault encrypt ansible/inventory/group_vars/all/vault.yml

# Test connectivity to all hosts
ansible -i ansible/inventory/hosts.yml linux_hosts -m ping

# Run baseline playbook
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/01-baseline.yml \
  --ask-vault-pass \
  -v

# Verify: SSH with password should now FAIL on all hosts
ssh -o PasswordAuthentication=yes labadmin@10.0.10.30  # Should be rejected
```

**✅ Checkpoint:** All hosts have Wazuh agent installed, SSH key-only, fail2ban running, logs shipping to rsyslog.

---

## Phase 6 — k3s Cluster (Day 3-4)
**Goal:** 4-node k3s cluster running with MetalLB, Traefik, Longhorn, cert-manager.

```bash
# Run k3s provisioning playbook
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/02-k3s.yml \
  --ask-vault-pass \
  -v

# Verify cluster from workstation
export KUBECONFIG=~/.kube/blerdmh-lab-config
kubectl get nodes
# Expected output:
# NAME              STATUS   ROLES                  AGE
# k3s-cp            Ready    control-plane,master   Xm
# k3s-worker-pi5    Ready    <none>                 Xm
# k3s-worker-amd    Ready    <none>                 Xm
# k3s-worker-n1     Ready    <none>                 Xm

kubectl get pods -A  # All system pods should be Running

# Apply namespaces
kubectl apply -f k3s/namespaces/namespaces.yml
```

**✅ Checkpoint:** `kubectl get nodes` shows 4 nodes Ready. MetalLB assigns IPs. Traefik ingress pod running.

---

## Phase 7 — Secrets & Cloudflare Tunnel (Day 4)
**Goal:** Sealed secrets created. Cloudflare tunnel connected. External access working.

```bash
# Create Cloudflare tunnel first (web UI):
# 1. Log into dash.cloudflare.com
# 2. Zero Trust → Access → Tunnels → Create tunnel
# 3. Name: blerdmh-lab
# 4. Copy the tunnel token

# Create and seal all secrets
chmod +x k3s/security/create-secrets.sh
bash k3s/security/create-secrets.sh

# Apply Cloudflare tunnel
kubectl apply -f k3s/ingress/cloudflare-tunnel.yml

# Check tunnel is connected:
kubectl logs -n ingress deployment/cloudflared

# Set up Cloudflare Access policy for Proxmox:
# Zero Trust → Access → Applications → Add application
# Type: Self-hosted
# URL: proxmox.blerdmh.com
# Policy: Require email = your@email.com (one-time PIN)
```

**✅ Checkpoint:** `https://grafana.blerdmh.com` loads from your phone (external network). Proxmox requires Cloudflare login.

---

## Phase 8 — Security Stack VMs (Day 4-5)
**Goal:** Wazuh, IDS, OpenVAS running and receiving data.

```bash
# Clone template and create security VMs on AMDPVE
qm clone 9000 100 --name wazuh-vm --full
qm set 100 --cores 8 --memory 16384 --net0 virtio,bridge=vmbr0,tag=40
qm set 100 --ipconfig0 ip=10.0.40.10/24,gw=10.0.40.1
qm resize 100 scsi0 +195G
qm start 100

# Repeat for ids-vm (101), openvas-vm (102), grafana-vm (103)
# See docs/01-PROXMOX-VM-LAYOUT.md for full commands

# Run Ansible security playbook
ansible-playbook -i ansible/inventory/hosts.yml \
  ansible/playbooks/03-security.yml \
  --ask-vault-pass

# Enable OPNsense syslog → Wazuh now that Wazuh is up
# OPNsense: System → Settings → Logging → Remote → 10.0.40.10:514
```

**✅ Checkpoint:** Wazuh dashboard at https://10.0.40.10 shows all agents online. OPNsense events appearing in Wazuh.

---

## Phase 9 — Personal Services (Day 5-6)
**Goal:** Nextcloud, Jellyfin, Home Assistant live.

```bash
# Apply all personal service manifests
kubectl apply -f k3s/personal/nextcloud.yml
kubectl apply -f k3s/personal/home-assistant.yml
kubectl apply -f k3s/media/jellyfin.yml
kubectl apply -f k3s/monitoring/monitoring-stack.yml

# Watch rollout
kubectl rollout status deployment/nextcloud -n personal
kubectl rollout status deployment/jellyfin -n media
kubectl rollout status deployment/homeassistant -n homeauto

# Add NFS provisioner for TrueNAS shares
helm repo add nfs-subdir-external-provisioner \
  https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/
helm install nfs-provisioner \
  nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
  --set nfs.server=10.0.20.20 \
  --set nfs.path=/mnt/tank \
  --set storageClass.name=nfs-media
```

**✅ Checkpoint:** All services accessible internally and externally via Cloudflare tunnel.

---

## Phase 10 — Red/Purple Team Lab (Day 6-7)
**Goal:** Windows AD lab online. Kali configured. Ready for exercises.

```bash
# Deploy Windows Server 2022 VM (manual install — no cloud-init)
# VMID 201, VLAN 62, 4 vCPU, 8GB RAM
# Install Windows Server 2022 Evaluation from ISO
# Configure as Active Directory Domain Controller
# Domain: lab.blerdmh.local

# Deploy Windows 11 workstation VM
# VMID 202, VLAN 62, join to domain

# Deploy Kali Linux VM
# VMID 200, VLAN 61, 4 vCPU, 8GB RAM
# Install from Kali ISO

# Verify Wazuh agents report from VLAN 62 VMs
# These are your portfolio detection targets
```

**✅ Final Checkpoint:** Full lab operational. All services running. Security stack collecting data from all VLANs. External services accessible via Cloudflare. Tailscale provides VPN access. Everything is in Git.

---

## Git Workflow

```bash
# Everything in this repo is IaC — commit every change
git add -A
git commit -m "feat: add nextcloud deployment manifest"
git push origin main

# NEVER commit plaintext secrets
# Sealed secrets (*-sealed.yml) are safe to commit
# ansible-vault encrypted files are safe to commit
```

## Useful Daily Commands

```bash
# Cluster status
kubectl get nodes
kubectl get pods -A
kubectl top nodes

# Restart a deployment
kubectl rollout restart deployment/nextcloud -n personal

# View logs
kubectl logs -n media deployment/jellyfin -f

# Port-forward for local testing (bypasses ingress)
kubectl port-forward -n monitoring svc/grafana 3000:3000

# Run Ansible against specific hosts
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/01-baseline.yml \
  --limit wazuh-vm

# Check Wazuh agent status on a host
sudo systemctl status wazuh-agent
sudo /var/ossec/bin/agent_control -l  # List agents on manager
```
