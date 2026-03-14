# blerdmh-lab

> Enterprise-grade cybersecurity home lab — fully reproducible via Infrastructure as Code.

**Stack:** OPNsense · Proxmox VE · k3s · TrueNAS Scale · Wazuh · Ansible · Helm  
**Domain:** blerdmh.com  
**External access:** Cloudflare Zero Trust Tunnel (zero open firewall ports)  
**VPN:** Tailscale subnet router

---

## Architecture Overview

```
Internet
   │
   ▼
Cloudflare Zero Trust (blerdmh.com)
   │ Tunnel — no open ports
   ▼
OPNsense Firewall (6-port 2.5GbE)
   │ VLAN trunk
   ▼
MokerLink 8-port PoE Managed Switch
   │
   ├── AMDPVE (Ryzen 9 7900X / 128GB)  — Security VMs, Red/Purple team
   ├── N1 Mini PVE (Ryzen 7 5825U / 16GB) — Personal services worker
   ├── ZimaBoard (TrueNAS Scale)        — NAS / persistent storage
   ├── Pi 4 8GB                         — k3s control plane + Tailscale router
   └── Pi 5 8GB                         — k3s worker (personal services)
```

## VLAN Segmentation

| VLAN | Name | Subnet | Purpose |
|------|------|--------|---------|
| 10 | MGMT | 10.0.10.0/24 | Proxmox, switches, admin |
| 20 | SERVERS | 10.0.20.0/24 | k3s cluster, NAS exports |
| 30 | CEPH_PUB | 10.0.30.0/24 | Ceph public network |
| 31 | CEPH_CLUSTER | 10.0.31.0/24 | Ceph heartbeat |
| 40 | SECURITY | 10.0.40.0/24 | Wazuh, IDS, OpenVAS |
| 50 | IOT | 10.0.50.0/24 | ESP32, Home Assistant hardware |
| 60 | PRODUCTION | 10.0.60.0/24 | Production services |
| 61 | RED_TEAM | 10.0.61.0/24 | Attack VMs (Kali) |
| 62 | PURPLE_TEAM | 10.0.62.0/24 | Target VMs (Windows AD) |
| 70 | GUEST | 10.0.70.0/24 | Untrusted / internet only |

## Services

### Externally accessible (via Cloudflare Access)
| Service | URL | Auth |
|---------|-----|------|
| Nextcloud | nextcloud.blerdmh.com | App login |
| Jellyfin | jellyfin.blerdmh.com | App login |
| Home Assistant | ha.blerdmh.com | App login |
| Grafana | grafana.blerdmh.com | App login |
| Proxmox | proxmox.blerdmh.com | Cloudflare Access + app login |

### Internal (Tailscale / MGMT VLAN only)
| Service | Address |
|---------|---------|
| Wazuh Dashboard | https://10.0.40.10 |
| OpenVAS | https://10.0.40.12:9392 |
| Proxmox AMDPVE | https://10.0.10.10:8006 |
| Proxmox N1 | https://10.0.10.11:8006 |
| TrueNAS | https://10.0.10.40 |

## Repository Structure

```
blerdmh-lab/
├── docs/
│   ├── 00-ARCHITECTURE.md      ← Full architecture reference
│   ├── 01-PROXMOX-VM-LAYOUT.md ← VM specs and network config
│   └── 02-REBUILD-GUIDE.md     ← Step-by-step bring-up guide
├── ansible/
│   ├── inventory/
│   │   └── hosts.yml           ← All hosts and variables
│   ├── roles/
│   │   ├── common/             ← Baseline hardening (all hosts)
│   │   └── k3s/                ← k3s install and config
│   └── playbooks/
│       ├── 00-site.yml         ← Master playbook
│       ├── 01-baseline.yml     ← OS hardening + Wazuh agents
│       └── 02-k3s.yml          ← k3s cluster + components
├── k3s/
│   ├── namespaces/             ← Namespace definitions
│   ├── ingress/                ← Traefik + Cloudflare tunnel
│   ├── personal/               ← Nextcloud, Home Assistant
│   ├── media/                  ← Jellyfin, Radarr, Sonarr, Lidarr
│   ├── monitoring/             ← Grafana, Prometheus, Loki, Promtail
│   └── security/               ← Secret management scripts
└── switch/
    ├── mokerlink-vlan-config.md   ← Switch port/VLAN reference
    └── opnsense-firewall-rules.md ← OPNsense rules per interface
```

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/blerdmh-lab.git
cd blerdmh-lab

# Follow docs/02-REBUILD-GUIDE.md — 10 phases, ~7 days to full lab
```

## Security Design Principles

- **Zero open ports** — all external access via Cloudflare tunnel
- **VLAN isolation** — red team cannot reach production (firewall enforced)
- **All hosts monitored** — Wazuh agent on every Linux host
- **Logs centralized** — all hosts ship to Wazuh + Loki
- **Secrets sealed** — kubeseal + ansible-vault, safe to commit
- **IaC everything** — reproducible from scratch in ~7 days

## Portfolio Projects Built on This Lab

1. **Detection Engineering** — Custom Sigma rules mapped to MITRE ATT&CK
2. **Active Directory Attack & Defense** — Full kill chain with Wazuh detections
3. **Honeypot Threat Intel Pipeline** — OpenCanary → MISP → OPNsense auto-block
4. **IoT Security Assessment** — ESP32 firmware analysis + traffic capture
5. **SOAR Automation** — Wazuh alert → enrichment → case creation pipeline

---

*Built for cybersecurity skill development and portfolio demonstration.*  
*Target roles: SOC Analyst · Security Engineer · Junior Penetration Tester*
