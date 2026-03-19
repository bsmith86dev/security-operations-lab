# MokerLink 8-Port PoE Managed Switch — VLAN Configuration
# blerdmh Lab | Switch IP: 10.0.10.2

## Overview
The MokerLink is an L2 smart managed switch. Configuration is done via web UI.
This document is the authoritative record of all port and VLAN settings.

---

## VLAN Database

Create these VLANs first under: Advanced > 802.1Q VLAN > VLAN Config

| VLAN ID | Name         |
|---------|--------------|
| 10      | MGMT         |
| 20      | SERVERS      |
| 30      | CEPH_PUB     |
| 31      | CEPH_CLUSTER |
| 40      | SECURITY     |
| 50      | IOT          |
| 60      | PRODUCTION   |
| 61      | RED_TEAM     |
| 62      | PURPLE_TEAM  |
| 70      | GUEST        |

---

## Port Configuration

### Port 1 — OPNsense ETH1 (Uplink / TRUNK)
**Mode:** TRUNK
**Native VLAN:** 10
**Tagged VLANs:** 20, 30, 31, 40, 50, 60, 61, 62, 70

This is the firewall uplink. ALL VLANs must be tagged here.
OPNsense will handle all inter-VLAN routing.

```
Port 1 VLAN Membership:
  VLAN 10  → UNTAGGED (native/PVID)
  VLAN 20  → TAGGED
  VLAN 30  → TAGGED
  VLAN 31  → TAGGED
  VLAN 40  → TAGGED
  VLAN 50  → TAGGED
  VLAN 60  → TAGGED
  VLAN 61  → TAGGED
  VLAN 62  → TAGGED
  VLAN 70  → TAGGED
```

---

### Port 2 — AMDPVE (Proxmox node — Ryzen 9 7900X)
**Mode:** TRUNK
**Native VLAN:** 10
**Tagged VLANs:** 20, 30, 40, 61, 62

AMDPVE hosts: Security stack VMs (VLAN 40), Red/Purple team VMs (61/62),
k3s heavy worker VM (VLAN 20), Ceph (VLAN 30).

```
Port 2 VLAN Membership:
  VLAN 10  → UNTAGGED (PVID — Proxmox management UI)
  VLAN 20  → TAGGED
  VLAN 30  → TAGGED
  VLAN 40  → TAGGED
  VLAN 61  → TAGGED
  VLAN 62  → TAGGED
```

---

### Port 3 — N1 Mini PVE (Proxmox node — Ryzen 7 5825U)
**Mode:** TRUNK
**Native VLAN:** 10
**Tagged VLANs:** 20, 30, 60, 70

N1 hosts: Personal services k3s worker VM (VLAN 20/60),
Ceph (VLAN 30), production workloads.

```
Port 3 VLAN Membership:
  VLAN 10  → UNTAGGED (PVID — Proxmox management UI)
  VLAN 20  → TAGGED
  VLAN 30  → TAGGED
  VLAN 60  → TAGGED
  VLAN 70  → TAGGED
```

---

### Port 4 — ZimaBoard (TrueNAS Scale)
**Mode:** TRUNK
**Native VLAN:** 10
**Tagged VLANs:** 20, 30, 60

ZimaBoard is NAS only. Needs MGMT for TrueNAS UI,
SERVERS (20) for NFS exports to k3s, CEPH_PUB (30), PRODUCTION (60).

```
Port 4 VLAN Membership:
  VLAN 10  → UNTAGGED (PVID — TrueNAS management UI)
  VLAN 20  → TAGGED
  VLAN 30  → TAGGED
  VLAN 60  → TAGGED
```

---

### Port 5 — TP-Link EAP720 (WiFi 7 AP)
**Mode:** TRUNK
**Native VLAN:** 10
**Tagged VLANs:** 60, 70

AP management on VLAN 10. SSIDs:
- "blerdmh-home" → VLAN 60 (Production)
- "blerdmh-guest" → VLAN 70 (Guest/untrusted)

```
Port 5 VLAN Membership:
  VLAN 10  → UNTAGGED (PVID — AP management)
  VLAN 60  → TAGGED
  VLAN 70  → TAGGED
```

---

### Port 6 — Workstation (Admin)
**Mode:** ACCESS
**VLAN:** 10 (MGMT)

Admin workstation gets MGMT access only.
10G traffic goes through NICGIGA unmanaged switch (separate).

```
Port 6 VLAN Membership:
  VLAN 10  → UNTAGGED (PVID)
```

---

### Port 7 — Raspberry Pi 4 (k3s control plane)
**Mode:** ACCESS
**VLAN:** 10 (MGMT)

Pi 4 management interface on VLAN 10.
Tailscale subnet router runs here.
Second NIC (USB-ethernet adapter) on VLAN 20 if available,
otherwise single-NIC with MGMT routing.

```
Port 7 VLAN Membership:
  VLAN 10  → UNTAGGED (PVID)
```

---

### Port 8 — Raspberry Pi 5 (k3s worker)
**Mode:** TRUNK
**Native VLAN:** 10
**Tagged VLANs:** 60

Pi 5 needs MGMT and access to production VLAN for workloads.

```
Port 8 VLAN Membership:
  VLAN 10  → UNTAGGED (PVID)
  VLAN 60  → TAGGED
```

---

## Switch Management Settings

| Setting | Value |
|---------|-------|
| Switch IP | 10.0.10.2 |
| Subnet | 255.255.255.0 |
| Gateway | 10.0.10.1 |
| Admin username | admin |
| Management VLAN | 10 |
| Spanning Tree | Enable (RSTP) |
| Port Mirroring | Port 1 → Port mirror NIC on AMDPVE (if adding IDS) |

---

## Port Summary Table

| Port | Device | Mode | Native | Tagged |
|------|--------|------|--------|--------|
| 1 | OPNsense ETH1 | TRUNK | 10 | 20,30,31,40,50,60,61,62,70 |
| 2 | AMDPVE | TRUNK | 10 | 20,30,40,61,62 |
| 3 | N1 Mini PVE | TRUNK | 10 | 20,30,60,70 |
| 4 | ZimaBoard | TRUNK | 10 | 20,30,60 |
| 5 | EAP720 AP | TRUNK | 10 | 60,70 |
| 6 | Workstation | ACCESS | 10 | — |
| 7 | Pi 4 (k3s-cp) | ACCESS | 10 | — |
| 8 | Pi 5 (k3s-w1) | TRUNK | 10 | 60 |

---

## NICGIGA Unmanaged Switch (Separate — 10G Fabric)

This switch is NOT managed. It provides a high-speed transfer fabric.
Connect these devices via SFP+ or 2.5G ports:

| Port | Device | Purpose |
|------|--------|---------|
| SFP+ 1 | AMDPVE 10G NIC | Storage/VM migration |
| SFP+ 2 | Workstation 10G NIC | Fast file transfer |
| 2.5G 1 | N1 Mini 2.5G port | Ceph / storage |
| 2.5G 2 | ZimaBoard 2.5G port | NAS transfers |

Traffic on this switch is UNTAGGED and uses the 10.0.30.x / 10.0.31.x
address space for Ceph, and direct host IPs for workstation transfers.
