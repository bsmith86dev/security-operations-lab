# security-operations-lab — Master Architecture Document
**Domain:** blerdmh.com (external) | lab.blerdmh.local / home.blerdmh.local (internal)
**Last Updated:** 2026-03-14
**Version:** 1.0 — Clean Rebuild

---

## Design Philosophy

This lab is designed to:
1. Mirror enterprise-grade infrastructure patterns
2. Be fully reproducible via IaC (Ansible + k3s manifests)
3. Support active cybersecurity skill development and portfolio projects
4. Expose selected services securely via Cloudflare Tunnel (zero open ports)
5. Provide complete observability across all VLANs

**Golden Rule:** If it isn't in Git, it doesn't exist.

---

## Physical Hardware Roles

| Device | Role | OS | VLAN Access |
|--------|------|----|-------------|
| Glovary i3-N355 (6-port) | Firewall / Router | OPNsense | All (trunk) |
| AMDPVE (Ryzen 9 7900X, 128GB) | Proxmox — Security + Heavy VMs | Proxmox VE 8.x | 10, 40, 61, 62 |
| N1 Mini (Ryzen 7 5825U, 16GB) | Proxmox — Personal + k3s worker VM | Proxmox VE 8.x | 10, 60, 70 |
| ZimaBoard 832 | NAS only | TrueNAS Scale | 10, 60 |
| Raspberry Pi 4 (8GB) | k3s control plane | Ubuntu 24.04 LTS | 10 |
| Raspberry Pi 5 (8GB) | k3s worker node | Ubuntu 24.04 LTS | 10, 60 |
| MokerLink 8-port PoE | Core managed switch | — | All VLANs |
| NICGIGA 2.5G unmanaged | 10G storage/transfer fabric | — | Untagged |
| TP-Link EAP720 | WiFi 7 AP | Omada | 10, 60, 70 |
| Workstation (9950X3D) | Admin workstation | Windows 11 | 10 |

---

## VLAN Design

| VLAN ID | Name | Subnet | Gateway | Purpose |
|---------|------|--------|---------|---------|
| 10 | MGMT | 10.0.10.0/24 | 10.0.10.1 | Management — Proxmox, switches, APs, admin workstation |
| 20 | SERVERS | 10.0.20.0/24 | 10.0.20.1 | k3s cluster nodes + NAS |
| 30 | CEPH_PUB | 10.0.30.0/24 | 10.0.30.1 | Ceph public network |
| 31 | CEPH_CLUSTER | 10.0.31.0/24 | — | Ceph cluster heartbeat (no gateway) |
| 40 | SECURITY | 10.0.40.0/24 | 10.0.40.1 | Wazuh, Suricata, Zeek, OpenVAS, IDS sensors |
| 50 | IOT | 10.0.50.0/24 | 10.0.50.1 | ESP32, Home Assistant hardware, IoT devices |
| 60 | PRODUCTION | 10.0.60.0/24 | 10.0.60.1 | Personal services — Nextcloud, Jellyfin, HA |
| 61 | RED_TEAM | 10.0.61.0/24 | 10.0.61.1 | Attack VMs, Kali, offensive tooling |
| 62 | PURPLE_TEAM | 10.0.62.0/24 | 10.0.62.1 | Target VMs, AD lab, detection validation |
| 70 | GUEST | 10.0.70.0/24 | 10.0.70.1 | Guest WiFi, untrusted devices |

### Key Changes from Previous Design
- VLAN 10 now serves as unified MGMT (was split 10/99)
- VLAN 20 (SERVERS) is new — dedicated to k3s nodes and NAS, off MGMT
- VLANs 30/31 retained for Ceph
- All other VLANs retained with same IDs

---

## Static IP Assignments

### VLAN 10 — MGMT
| IP | Device | Role |
|----|--------|------|
| 10.0.10.1 | OPNsense | Gateway |
| 10.0.10.2 | MokerLink switch | Management UI |
| 10.0.10.3 | TP-Link EAP720 | AP management |
| 10.0.10.10 | AMDPVE | Proxmox web UI |
| 10.0.10.11 | N1 Mini PVE | Proxmox web UI |
| 10.0.10.20 | Workstation | Admin |
| 10.0.10.30 | Pi 4 | k3s control plane (mgmt NIC) |
| 10.0.10.31 | Pi 5 | k3s worker (mgmt NIC) |
| 10.0.10.40 | ZimaBoard | TrueNAS UI |

### VLAN 20 — SERVERS
| IP | Device | Role |
|----|--------|------|
| 10.0.20.1 | OPNsense | Gateway |
| 10.0.20.10 | k3s-cp (Pi 4) | Control plane cluster NIC |
| 10.0.20.11 | k3s-worker-pi5 | Pi 5 worker |
| 10.0.20.12 | k3s-worker-amd (VM on AMDPVE) | Heavy worker |
| 10.0.20.13 | k3s-worker-n1 (VM on N1) | Worker |
| 10.0.20.20 | ZimaBoard | NFS/SMB exports |
| 10.0.20.100-200 | k3s LoadBalancer pool | MetalLB range |

### VLAN 40 — SECURITY
| IP | Device | Role |
|----|--------|------|
| 10.0.40.1 | OPNsense | Gateway |
| 10.0.40.10 | Wazuh Manager VM | SIEM/EDR (on AMDPVE) |
| 10.0.40.11 | Suricata/Zeek VM | IDS/NSM (on AMDPVE) |
| 10.0.40.12 | OpenVAS VM | Vulnerability scanner (on AMDPVE) |
| 10.0.40.13 | Grafana VM | Dashboards + metrics (on AMDPVE) |

### VLAN 60 — PRODUCTION
| IP | Device | Role |
|----|--------|------|
| 10.0.60.1 | OPNsense | Gateway |
| 10.0.60.10 | k3s LoadBalancer VIP — Traefik | Ingress controller |
| 10.0.60.20 | ZimaBoard NFS | Storage for production PVCs |

---

## k3s Cluster Architecture

```
┌─────────────────────────────────────────────────┐
│                 k3s Cluster                      │
│                                                  │
│  ┌──────────────┐    ┌───────────────────────┐  │
│  │  Pi 4 8GB    │    │  Pi 5 8GB             │  │
│  │  Control     │    │  Worker (light loads) │  │
│  │  Plane       │    │  Nextcloud, HA        │  │
│  │  10.0.20.10  │    │  10.0.20.11           │  │
│  └──────────────┘    └───────────────────────┘  │
│                                                  │
│  ┌──────────────┐    ┌───────────────────────┐  │
│  │  AMDPVE VM   │    │  N1 Mini VM           │  │
│  │  Heavy worker│    │  Worker               │  │
│  │  Wazuh,      │    │  Jellyfin, media      │  │
│  │  OpenVAS     │    │  10.0.20.13           │  │
│  │  10.0.20.12  │    │                       │  │
│  └──────────────┘    └───────────────────────┘  │
└─────────────────────────────────────────────────┘
```

**Storage:** Longhorn distributed storage across worker nodes
**Ingress:** Traefik v3 with Cloudflare tunnel backend
**Load Balancer:** MetalLB (pool: 10.0.20.100–200)
**CNI:** Flannel (k3s default)
**Secrets:** Sealed Secrets (kubeseal)

---

## External Access Architecture

```
Internet
   │
   ▼
Cloudflare (blerdmh.com)
   │  Zero Trust Tunnel (cloudflared)
   │  No open ports on firewall
   ▼
Traefik Ingress (k3s)
   │
   ├── nextcloud.blerdmh.com  → Nextcloud
   ├── jellyfin.blerdmh.com   → Jellyfin
   ├── ha.blerdmh.com         → Home Assistant
   ├── grafana.blerdmh.com    → Grafana
   └── proxmox.blerdmh.com    → Proxmox UI (CF Access policy)
```

**Tailscale** is deployed as a subnet router on the Pi 4, advertising:
- 10.0.10.0/24 (MGMT)
- 10.0.20.0/24 (SERVERS)
- 10.0.40.0/24 (SECURITY)

This gives you VPN access to all management interfaces without Cloudflare.

---

## Service Map

### Security Stack (VLAN 40 VMs on AMDPVE)
| Service | VM | IP | Port |
|---------|----|----|------|
| Wazuh Manager | wazuh-vm | 10.0.40.10 | 1514/1515/55000 |
| Wazuh Dashboard | wazuh-vm | 10.0.40.10 | 443 |
| OpenSearch | wazuh-vm | 10.0.40.10 | 9200 |
| Suricata | ids-vm | 10.0.40.11 | — (passive) |
| Zeek | ids-vm | 10.0.40.11 | — (passive) |
| OpenVAS/Greenbone | openvas-vm | 10.0.40.12 | 9392 |
| Grafana | grafana-vm | 10.0.40.13 | 3000 |
| Prometheus | grafana-vm | 10.0.40.13 | 9090 |

### Personal Services (k3s — VLAN 60)
| Service | Namespace | External URL |
|---------|-----------|--------------|
| Nextcloud | personal | nextcloud.blerdmh.com |
| Jellyfin | media | jellyfin.blerdmh.com |
| Home Assistant | homeauto | ha.blerdmh.com |
| Radarr | media | internal only |
| Sonarr | media | internal only |
| Lidarr | media | internal only |

### Monitoring (k3s — VLAN 60 + SECURITY feeds)
| Service | Namespace | External URL |
|---------|-----------|--------------|
| Grafana | monitoring | grafana.blerdmh.com |
| Prometheus | monitoring | internal only |
| Loki | monitoring | internal only |
| Promtail | monitoring | DaemonSet on all nodes |

---

## Git Repository Structure

```
                                ← This repo
├── docs/                       ← Architecture docs
├── ansible/                    ← Provisioning automation
│   ├── inventory/
│   ├── roles/
│   └── playbooks/
├── k3s/                        ← Kubernetes manifests
│   ├── namespaces/
│   ├── ingress/
│   ├── security/
│   ├── personal/
│   └── monitoring/
└── switch/                     ← Switch/firewall configs
```
