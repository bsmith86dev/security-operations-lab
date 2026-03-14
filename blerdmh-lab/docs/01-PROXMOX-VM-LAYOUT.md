# Proxmox VM & LXC Layout — blerdmh Lab
# Authoritative record of all VMs and containers

---

## AMDPVE Node (Ryzen 9 7900X | 128GB DDR5 | 2TB NVMe)
**Role:** Security stack + Red/Purple team VMs + k3s heavy worker

### VM Allocation

| VMID | Name | Type | vCPU | RAM | Disk | VLAN | Role |
|------|------|------|------|-----|------|------|------|
| 100 | wazuh-vm | VM | 8 | 16GB | 200GB | 40 | Wazuh SIEM + OpenSearch |
| 101 | ids-vm | VM | 4 | 8GB | 100GB | 40 | Suricata + Zeek |
| 102 | openvas-vm | VM | 4 | 8GB | 100GB | 40 | OpenVAS/Greenbone |
| 103 | grafana-vm | VM | 4 | 8GB | 50GB | 40 | Grafana + Prometheus |
| 110 | k3s-worker-amd | VM | 8 | 16GB | 200GB | 20 | k3s heavy worker |
| 200 | kali-red | VM | 4 | 8GB | 100GB | 61 | Kali Linux (red team) |
| 201 | win-target | VM | 4 | 8GB | 100GB | 62 | Windows Server 2022 AD |
| 202 | win-workstation | VM | 2 | 4GB | 60GB | 62 | Windows 11 (AD target) |

**Total AMDPVE usage:** ~76GB RAM / 128GB | ~910GB disk / ~2TB

---

## N1 Mini Node (Ryzen 7 5825U | 16GB DDR4 | 512GB NVMe)
**Role:** Personal services k3s worker + light VMs

### VM Allocation

| VMID | Name | Type | vCPU | RAM | Disk | VLAN | Role |
|------|------|------|------|-----|------|------|------|
| 300 | k3s-worker-n1 | VM | 6 | 10GB | 200GB | 20 | k3s worker (media/personal) |
| 301 | pihole | LXC | 1 | 512MB | 8GB | 10 | Secondary DNS (optional) |

**Total N1 usage:** ~10.5GB RAM / 16GB | ~208GB disk / 512GB

---

## Proxmox Network Configuration

Each VM needs virtual network interfaces mapped to the correct VLAN.
In Proxmox, use Linux Bridge with VLAN-aware enabled on the bridge.

### Bridge Setup on Each Proxmox Node

```bash
# /etc/network/interfaces — AMDPVE example
# Run: nano /etc/network/interfaces

auto lo
iface lo inet loopback

# Physical NIC — trunk from MokerLink
auto eno1
iface eno1 inet manual

# VLAN-aware bridge — single bridge handles ALL VLANs
auto vmbr0
iface vmbr0 inet static
    address 10.0.10.10/24
    gateway 10.0.10.1
    bridge-ports eno1
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 2-4094

# 10G NIC for Ceph/storage fabric (NICGIGA)
auto eno2
iface eno2 inet static
    address 10.0.30.10/24
```

### VM Network Interface → VLAN Mapping

When creating VMs in Proxmox, set the VLAN tag on the network device:

```
VM 100 (wazuh-vm):
  net0: virtio, bridge=vmbr0, tag=40

VM 110 (k3s-worker-amd):
  net0: virtio, bridge=vmbr0, tag=20

VM 200 (kali-red):
  net0: virtio, bridge=vmbr0, tag=61

VM 201 (win-target):
  net0: virtio, bridge=vmbr0, tag=62
  # Also add a second NIC for MGMT access during setup:
  net1: virtio, bridge=vmbr0, tag=10
```

---

## Security VM Deployment Guide

### Wazuh VM (VMID 100) — Ubuntu 22.04 LTS

**Specs:** 8 vCPU | 16GB RAM | 200GB disk | VLAN 40 | IP: 10.0.40.10

```bash
# After OS install and Ansible baseline, install Wazuh all-in-one:
curl -sO https://packages.wazuh.com/4.7/wazuh-install.sh
curl -sO https://packages.wazuh.com/4.7/config.yml

# Edit config.yml — set node IPs to 10.0.40.10
# Then run:
bash wazuh-install.sh --generate-config-files
bash wazuh-install.sh --wazuh-indexer node-1
bash wazuh-install.sh --start-cluster
bash wazuh-install.sh --wazuh-server wazuh-1
bash wazuh-install.sh --wazuh-dashboard wazuh-1

# Access dashboard: https://10.0.40.10
# Default creds printed at end of install
```

**Post-install:** Enable OPNsense syslog forwarding to 10.0.40.10:514

---

### IDS VM (VMID 101) — Ubuntu 22.04 LTS

**Specs:** 4 vCPU | 8GB RAM | 100GB disk | VLAN 40 | IP: 10.0.40.11

```bash
# Suricata
apt install -y suricata
suricata-update  # Pull ET Open rules

# Configure to monitor VLAN 40 interface
# /etc/suricata/suricata.yaml
# af-packet:
#   - interface: eth0

# Zeek
apt install -y zeek
# /etc/zeek/node.cfg — set interface=eth0

# Both log to /var/log — Wazuh agent ships to 10.0.40.10
```

**For inter-VLAN monitoring:** Configure a SPAN/mirror port on MokerLink
pointing to this VM's interface. This gives Zeek visibility into all
east-west traffic between VLANs — the most valuable IDS placement.

---

### OpenVAS VM (VMID 102) — Ubuntu 22.04 LTS

**Specs:** 4 vCPU | 8GB RAM | 100GB disk | VLAN 40 | IP: 10.0.40.12

```bash
# Greenbone Community Edition
curl -f -L https://greenbone.github.io/docs/latest/_static/setup-and-start-greenbone-community-edition.sh \
  -o setup-greenbone.sh
bash setup-greenbone.sh

# Access: https://10.0.40.12:9392
# Default: admin / (printed during setup)

# After setup, create scan targets for each VLAN:
# - 10.0.20.0/24 (servers)
# - 10.0.60.0/24 (production)
# - 10.0.62.0/24 (purple team)
```

---

## k3s Worker VMs — Cloud-Init Template

Create a reusable Ubuntu 22.04 cloud-init template in Proxmox:

```bash
# Run on each Proxmox node
wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img

qm create 9000 --name ubuntu-2204-template --memory 2048 --cores 2 \
  --net0 virtio,bridge=vmbr0 --ostype l26

qm importdisk 9000 jammy-server-cloudimg-amd64.img local-lvm
qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0
qm set 9000 --ide2 local-lvm:cloudinit
qm set 9000 --boot c --bootdisk scsi0
qm set 9000 --serial0 socket --vga serial0
qm set 9000 --agent enabled=1
qm set 9000 --ipconfig0 ip=dhcp
qm set 9000 --sshkey ~/.ssh/lab_ed25519.pub
qm template 9000

# Clone for each worker VM:
qm clone 9000 110 --name k3s-worker-amd --full
qm set 110 --cores 8 --memory 16384 --net0 virtio,bridge=vmbr0,tag=20
qm resize 110 scsi0 +195G
qm set 110 --ipconfig0 ip=10.0.20.12/24,gw=10.0.20.1
qm start 110
```

---

## ZimaBoard — TrueNAS Scale

**Role:** NAS only. Hosts all persistent storage.

### Dataset Layout

```
tank/                    ← Main pool (16TB WD + 8TB Seagate)
├── media/               → NFS export → k3s media namespace
│   ├── movies/
│   ├── tv/
│   └── music/
├── nextcloud/           → NFS export → k3s personal namespace
├── backups/             → Backup target (Proxmox backups, config backups)
├── ceph/                → Ceph OSD (if ZimaBoard joins Ceph — optional)
└── isos/                → Proxmox ISO storage

fast/                    ← Fast pool (1TB Crucial P310 NVMe)
└── k8s-volumes/         → NFS export → Longhorn backup target
```

### NFS Exports (TrueNAS UI → Shares → NFS)

| Path | Network | Options |
|------|---------|---------|
| /mnt/tank/media | 10.0.20.0/24 | ro for Jellyfin, rw for *arr apps |
| /mnt/tank/nextcloud | 10.0.20.0/24 | rw |
| /mnt/tank/backups | 10.0.10.0/24, 10.0.20.0/24 | rw |
| /mnt/fast/k8s-volumes | 10.0.20.0/24 | rw |
