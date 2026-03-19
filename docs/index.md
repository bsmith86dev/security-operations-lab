# blerdmh Lab

**Enterprise-grade cybersecurity home lab — fully reproducible via Infrastructure as Code.**

---

## What this is

A production-quality home lab built for:

- Developing real SOC analyst, security engineering, and penetration testing skills
- Building a portfolio of cybersecurity projects that demonstrate technical depth
- Hosting personal services (Nextcloud, Jellyfin, Home Assistant) with enterprise-grade security controls
- Practicing detection engineering, incident response, and threat hunting

Everything in this lab is defined as code, versioned in Git, and deployed automatically through CI/CD pipelines.

---

## Quick links

| Resource | Location |
|----------|----------|
| Architecture overview | [docs/architecture](docs/00-ARCHITECTURE.md) |
| Rebuild guide (start here) | [docs/rebuild-guide](docs/02-REBUILD-GUIDE.md) |
| Switch & firewall config | [switch/](switch/mokerlink-vlan-config.md) |
| k3s manifests | [k3s/](k3s/namespaces/namespaces.yml) |
| Ansible playbooks | [ansible/](ansible/playbooks/) |
| CI/CD pipeline | [docs/cicd/](docs/cicd/overview.md) |
| Service inventory | [service-inventory](service-inventory.md) |
| Portfolio projects | [portfolio-projects](portfolio-projects.md) |

---

## Stack at a glance

```
External access ──► Cloudflare Zero Trust Tunnel (zero open ports)
VPN access      ──► Tailscale subnet router (Pi 4)
Firewall        ──► OPNsense on Glovary i3-N355 (6x 2.5GbE)
Switching       ──► MokerLink 8-port PoE managed (10 VLANs)
Compute         ──► AMDPVE (Ryzen 9 7900X / 128GB) + N1 Mini (Ryzen 7 / 16GB)
Containers      ──► k3s cluster (Pi4 CP + Pi5 + 2x VM workers)
Storage         ──► TrueNAS Scale on ZimaBoard (NFS exports to k3s)
GPU             ──► AMD RX 5700 XT → k3s-worker-amd (Jellyfin VAAPI)
SIEM            ──► Wazuh (all-in-one: manager + OpenSearch + dashboard)
IDS/NSM         ──► Suricata + Zeek (VLAN 40, SPAN port monitoring)
Vuln scanning   ──► OpenVAS / Greenbone CE
Monitoring      ──► Grafana + Prometheus + Loki + Promtail
```

---

## VLAN segmentation

| VLAN | Name | Subnet | Purpose |
|------|------|--------|---------|
| 10 | MGMT | 10.0.10.0/24 | Management — Proxmox, switch, admin workstation |
| 20 | SERVERS | 10.0.20.0/24 | k3s cluster nodes, NAS exports |
| 30 | CEPH_PUB | 10.0.30.0/24 | Ceph public network |
| 31 | CEPH_CLUSTER | 10.0.31.0/24 | Ceph cluster heartbeat |
| 40 | SECURITY | 10.0.40.0/24 | Wazuh, Suricata, Zeek, OpenVAS |
| 50 | IOT | 10.0.50.0/24 | ESP32, Home Assistant hardware |
| 60 | PRODUCTION | 10.0.60.0/24 | Production services |
| 61 | RED_TEAM | 10.0.61.0/24 | Attack VMs — Kali Linux |
| 62 | PURPLE_TEAM | 10.0.62.0/24 | Target VMs — Windows AD lab |
| 70 | GUEST | 10.0.70.0/24 | Guest WiFi — internet only |

---

## Repository layout

```
blerdmh-lab/
├── .github/
│   ├── workflows/        ← 5 GitHub Actions pipelines
│   └── scripts/          ← CI helper scripts
├── ansible/
│   ├── inventory/        ← Hosts, group vars, vault
│   ├── roles/            ← common, k3s, proxmox, security, gitea
│   └── playbooks/        ← 00-site through 06-gitea
├── k3s/
│   ├── namespaces/       ← Namespace definitions
│   ├── ingress/          ← Traefik, Cloudflare tunnel, cert-manager
│   ├── personal/         ← Nextcloud, Home Assistant
│   ├── media/            ← Jellyfin (GPU), Radarr, Sonarr, Lidarr
│   ├── monitoring/       ← Grafana, Prometheus, Loki, Promtail
│   ├── security/         ← AMD GPU device plugin, secret scripts
│   └── network-policy/   ← Kubernetes NetworkPolicy manifests
├── switch/
│   ├── mokerlink-vlan-config.md
│   └── opnsense-firewall-rules.md
└── docs/                 ← This documentation site
```

---

*Target roles: SOC Analyst · Security Engineer · Junior Penetration Tester · Detection Engineer*
