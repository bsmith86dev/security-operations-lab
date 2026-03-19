# OPNsense Firewall Rules — blerdmh Lab
# Version: 1.0 | Updated: 2026-03-14

## Interface Assignments

| OPNsense Interface | VLAN | Physical/Virtual |
|-------------------|------|-----------------|
| WAN | — | ETH0 → ISP modem |
| LAN (MGMT) | 10 | ETH1.10 |
| SERVERS | 20 | ETH1.20 |
| CEPH_PUB | 30 | ETH1.30 |
| CEPH_CLUSTER | 31 | ETH1.31 |
| SECURITY | 40 | ETH1.40 |
| IOT | 50 | ETH1.50 |
| PRODUCTION | 60 | ETH1.60 |
| RED_TEAM | 61 | ETH1.61 |
| PURPLE_TEAM | 62 | ETH1.62 |
| GUEST | 70 | ETH1.70 |

ETH1 carries all VLANs as a trunk to the MokerLink switch.

---

## Aliases (Create these first under Firewall > Aliases)

```
Name: RFC1918
Type: Network
Networks: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
Description: All private IP ranges

Name: MGMT_HOSTS
Type: Host
Hosts: 10.0.10.20 (workstation), 10.0.10.1 (OPNsense)
Description: Authorized management sources

Name: K3S_NODES
Type: Network
Networks: 10.0.20.10, 10.0.20.11, 10.0.20.12, 10.0.20.13
Description: k3s cluster nodes

Name: NAS_HOST
Type: Host
Hosts: 10.0.20.20
Description: ZimaBoard TrueNAS

Name: SECURITY_VMS
Type: Network
Networks: 10.0.40.10, 10.0.40.11, 10.0.40.12, 10.0.40.13
Description: Security stack VMs

Name: DNS_SERVERS
Type: Host
Hosts: 10.0.10.1
Description: OPNsense DNS resolver
```

---

## Firewall Rules by Interface

Rules are processed top-to-bottom. First match wins.
Direction: IN on each interface (traffic coming FROM that network).

---

### WAN Interface
```
# Block all inbound by default (OPNsense default — verify this is set)
# No explicit allow rules on WAN — Cloudflare tunnel is outbound only
# Tailscale is outbound only

Action  Proto  Source  Dest    Port   Description
BLOCK   *      *       *       *      Default deny all inbound (implicit)
```

---

### MGMT (VLAN 10) — 10.0.10.0/24
```
# Management network — most trusted, but still scoped

Action  Proto  Source        Dest              Port        Description
PASS    TCP    10.0.10.20    10.0.10.2         80,443      Workstation → switch UI
PASS    TCP    10.0.10.20    10.0.10.3         80,443      Workstation → AP UI
PASS    TCP    10.0.10.20    10.0.10.10        8006        Workstation → AMDPVE UI
PASS    TCP    10.0.10.20    10.0.10.11        8006        Workstation → N1 PVE UI
PASS    TCP    10.0.10.20    10.0.10.40        80,443      Workstation → TrueNAS UI
PASS    TCP    10.0.10.20    10.0.40.10        443,55000   Workstation → Wazuh
PASS    TCP    10.0.10.20    10.0.40.12        9392        Workstation → OpenVAS
PASS    TCP    10.0.10.20    10.0.40.13        3000        Workstation → Grafana
PASS    TCP    MGMT_HOSTS    10.0.20.0/24      22          SSH to k3s nodes / NAS
PASS    UDP    10.0.10.0/24  *                 53          DNS to OPNsense
PASS    TCP    10.0.10.0/24  *                 80,443      Internet access (updates)
PASS    *      10.0.10.30    *                 *           Tailscale router (Pi4)
BLOCK   *      10.0.10.0/24  RFC1918           *           Block MGMT → other private (except above)
PASS    *      10.0.10.0/24  !RFC1918          *           Allow MGMT internet
```

---

### SERVERS (VLAN 20) — 10.0.20.0/24
```
# k3s nodes and NAS — controlled access

Action  Proto  Source          Dest              Port        Description
PASS    TCP    K3S_NODES       K3S_NODES         *           k3s intra-cluster (all ports)
PASS    TCP    K3S_NODES       NAS_HOST          2049,445    NFS and SMB from k3s
PASS    UDP    K3S_NODES       NAS_HOST          2049        NFS UDP
PASS    TCP    K3S_NODES       10.0.40.10        1514,1515   Wazuh agent → manager
PASS    UDP    K3S_NODES       DNS_SERVERS       53          DNS
PASS    TCP    K3S_NODES       *                 80,443      Internet (image pulls, updates)
PASS    TCP    MGMT_HOSTS      K3S_NODES         22,6443     SSH + kubectl API
PASS    TCP    NAS_HOST        10.0.40.10        1514,1515   NAS Wazuh agent
PASS    TCP    10.0.20.0/24    10.0.60.0/24      80,443,8096 Services → production
BLOCK   *      10.0.20.0/24    10.0.40.0/24      *           Servers cannot query security (except Wazuh above)
BLOCK   *      10.0.20.0/24    10.0.61.0/24      *           Block servers → red team
BLOCK   *      10.0.20.0/24    10.0.62.0/24      *           Block servers → purple team
BLOCK   *      10.0.20.0/24    RFC1918           *           Block all other RFC1918
PASS    *      10.0.20.0/24    !RFC1918          *           Allow internet
```

---

### SECURITY (VLAN 40) — 10.0.40.0/24
```
# Security stack — can REACH all VLANs for monitoring, nothing reaches in except agents

Action  Proto  Source            Dest              Port          Description
PASS    UDP    10.0.40.10        *                 514           Syslog collection (all VLANs)
PASS    TCP    10.0.40.10        *                 514           Syslog TCP collection
PASS    TCP    10.0.40.10        RFC1918           *             Wazuh manager → any (active response)
PASS    TCP    10.0.40.11        RFC1918           *             IDS/NSM reach all segments
PASS    TCP    10.0.40.12        RFC1918           *             OpenVAS scan any segment
PASS    TCP    10.0.40.12        !RFC1918          *             OpenVAS internet
PASS    TCP    10.0.40.13        RFC1918           9090,3100     Grafana → Prometheus/Loki
PASS    UDP    10.0.40.0/24      DNS_SERVERS       53            DNS
PASS    TCP    10.0.40.0/24      !RFC1918          80,443        Internet (updates, threat intel)
PASS    TCP    MGMT_HOSTS        10.0.40.0/24      *             Admin access to security tools
# Wazuh agent ingress (agents initiate outbound, but manager responds)
PASS    TCP    *                 10.0.40.10        1514,1515     Wazuh agent enrollment
BLOCK   *      10.0.40.0/24     10.0.61.0/24      *             Security cannot touch red team
```

---

### IOT (VLAN 50) — 10.0.50.0/24
```
# Maximally isolated — internet for updates only, DNS to OPNsense only

Action  Proto  Source          Dest              Port    Description
PASS    UDP    10.0.50.0/24    DNS_SERVERS       53      DNS only to OPNsense
PASS    TCP    10.0.50.0/24    10.0.60.10        8123    IoT → Home Assistant only
PASS    TCP    10.0.50.0/24    !RFC1918          80,443  Internet for firmware updates
PASS    TCP    10.0.50.0/24    10.0.40.10        1514    Wazuh agent (if deployed)
BLOCK   *      10.0.50.0/24    RFC1918           *       No access to any internal VLAN except HA
```

---

### PRODUCTION (VLAN 60) — 10.0.60.0/24
```
# Production services — accessible from internal, exposed via Cloudflare externally

Action  Proto  Source          Dest              Port          Description
PASS    TCP    10.0.60.0/24    10.0.20.20        2049,445      Prod → NAS storage
PASS    TCP    10.0.60.0/24    10.0.40.10        1514,1515     Wazuh agents
PASS    UDP    10.0.60.0/24    DNS_SERVERS       53            DNS
PASS    TCP    10.0.60.0/24    !RFC1918          80,443        Internet
PASS    TCP    10.0.10.0/24    10.0.60.0/24      *             MGMT → production (admin)
PASS    TCP    10.0.50.0/24    10.0.60.10        8123          IoT → Home Assistant
BLOCK   *      10.0.60.0/24    10.0.61.0/24      *             Production cannot reach red team
BLOCK   *      10.0.60.0/24    10.0.62.0/24      *             Production cannot reach purple team
BLOCK   *      10.0.60.0/24    RFC1918           *             Block all other internal
```

---

### RED_TEAM (VLAN 61) — 10.0.61.0/24
```
# Attack lab — ONLY reaches purple team targets and internet

Action  Proto  Source          Dest              Port    Description
PASS    *      10.0.61.0/24    10.0.62.0/24      *       Red → Purple team targets ONLY
PASS    UDP    10.0.61.0/24    DNS_SERVERS       53      DNS
PASS    TCP    10.0.61.0/24    !RFC1918          80,443  Internet (tool downloads, C2 infra)
BLOCK   *      10.0.61.0/24    RFC1918           *       Block all other internal (CRITICAL)
```

---

### PURPLE_TEAM (VLAN 62) — 10.0.62.0/24
```
# Target lab — accepts red team attacks, feeds logs to security

Action  Proto  Source          Dest              Port          Description
PASS    *      10.0.61.0/24    10.0.62.0/24      *             Accept red team attacks
PASS    TCP    10.0.62.0/24    10.0.40.10        1514,1515     Wazuh agents (CRITICAL for detections)
PASS    UDP    10.0.62.0/24    DNS_SERVERS       53            DNS
PASS    TCP    10.0.62.0/24    !RFC1918          80,443        Internet (Windows updates, etc)
PASS    TCP    MGMT_HOSTS      10.0.62.0/24      22,3389,8006  Admin access (SSH, RDP, Proxmox console)
BLOCK   *      10.0.62.0/24    10.0.60.0/24      *             Purple cannot reach production
BLOCK   *      10.0.62.0/24    10.0.10.0/24      *             Purple cannot reach MGMT
BLOCK   *      10.0.62.0/24    RFC1918           *             Block all other internal
```

---

### GUEST (VLAN 70) — 10.0.70.0/24
```
# Maximally isolated — internet only

Action  Proto  Source          Dest        Port    Description
PASS    UDP    10.0.70.0/24    DNS_SERVERS 53      DNS
PASS    TCP    10.0.70.0/24    !RFC1918    80,443  Internet only
BLOCK   *      10.0.70.0/24    RFC1918     *       Block all internal access
```

---

## DNS Configuration (OPNsense Unbound)

Set under Services > Unbound DNS > Host Overrides:

```
# Internal DNS overrides — lab.blerdmh.local

proxmox-amd.lab.blerdmh.local   → 10.0.10.10
proxmox-n1.lab.blerdmh.local    → 10.0.10.11
truenas.lab.blerdmh.local       → 10.0.10.40
wazuh.lab.blerdmh.local         → 10.0.40.10
openvas.lab.blerdmh.local       → 10.0.40.12
grafana.lab.blerdmh.local       → 10.0.40.13
k3s-cp.lab.blerdmh.local        → 10.0.10.30
switch.lab.blerdmh.local        → 10.0.10.2
ap.lab.blerdmh.local            → 10.0.10.3

# Production services — resolve internally to k3s ingress
nextcloud.blerdmh.com           → 10.0.20.100 (MetalLB VIP)
jellyfin.blerdmh.com            → 10.0.20.100
ha.blerdmh.com                  → 10.0.20.100
grafana.blerdmh.com             → 10.0.40.13
```

---

## OPNsense Services to Enable

1. **Suricata** — on VLAN 10 (MGMT) and VLAN 40 (SECURITY) interfaces, ET Open ruleset
2. **Unbound DNS** — with DNSSEC, blocking malvertising categories
3. **DHCP Server** — static leases for all known devices, dynamic range for guests
4. **Syslog** — forward OPNsense logs to Wazuh (10.0.40.10:514)
5. **Netflow** — export to Grafana/ntopng if desired
6. **Cloudflare DDNS** — update blerdmh.com if your WAN IP changes (even though tunnel is preferred)
