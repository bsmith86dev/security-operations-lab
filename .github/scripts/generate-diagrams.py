#!/usr/bin/env python3
"""
.github/scripts/generate-diagrams.py
Generates Mermaid diagrams from k3s manifests and network config.
Called by 04-docs.yml workflow before MkDocs build.
Output goes into docs/ as .md files with mermaid fenced code blocks.
"""

import os
import re
import yaml
from pathlib import Path

DOCS_DIR = Path("docs")
K3S_DIR = Path("k3s")


def load_yaml_file(path):
    """Load a potentially multi-document YAML file."""
    docs = []
    try:
        with open(path) as f:
            for doc in yaml.safe_load_all(f):
                if doc:
                    docs.append(doc)
    except Exception as e:
        print(f"  Warning: could not parse {path}: {e}")
    return docs


def get_deployments():
    """Walk k3s manifests and extract all Deployment resources."""
    deployments = []
    for yml_file in K3S_DIR.rglob("*.yml"):
        if "sealed" in yml_file.name or "values" in yml_file.name:
            continue
        for doc in load_yaml_file(yml_file):
            if doc.get("kind") == "Deployment":
                namespace = doc.get("metadata", {}).get("namespace", "default")
                name = doc.get("metadata", {}).get("name", "unknown")
                containers = doc.get("spec", {}).get("template", {}).get(
                    "spec", {}).get("containers", [])
                image = containers[0].get("image", "unknown") if containers else "unknown"
                deployments.append({
                    "name": name,
                    "namespace": namespace,
                    "image": image.split(":")[0].split("/")[-1],
                    "file": str(yml_file),
                })
    return deployments


def generate_service_graph():
    """Generate a Mermaid graph of all services by namespace."""
    deployments = get_deployments()

    # Group by namespace
    by_ns = {}
    for d in deployments:
        by_ns.setdefault(d["namespace"], []).append(d)

    ns_colors = {
        "personal":  "#1D9E75",
        "media":     "#BA7517",
        "homeauto":  "#7F77DD",
        "monitoring":"#185FA5",
        "ingress":   "#3B6D11",
        "security":  "#A32D2D",
    }

    lines = ["graph TB"]
    lines.append("    CF[\"☁️ Cloudflare\"] --> TR[\"Traefik Ingress\"]")
    lines.append("    TS[\"🔒 Tailscale Router\"] -.->|VPN| TR")
    lines.append("")

    for ns, svcs in sorted(by_ns.items()):
        color = ns_colors.get(ns, "#5F5E5A")
        lines.append(f"    subgraph {ns}[\"{ns} namespace\"]")
        for svc in svcs:
            safe_id = f"{ns}_{svc['name'].replace('-', '_')}"
            lines.append(f"        {safe_id}[\"{svc['name']}\"]")
        lines.append("    end")
        lines.append("")
        # Connect traefik to services with ingress
        for svc in svcs:
            safe_id = f"{ns}_{svc['name'].replace('-', '_')}"
            lines.append(f"    TR --> {safe_id}")

    lines.append("")
    lines.append("    style ingress fill:#3B6D11,color:#fff")
    lines.append("    style monitoring fill:#185FA5,color:#fff")
    lines.append("    style personal fill:#1D9E75,color:#fff")
    lines.append("    style media fill:#BA7517,color:#fff")
    lines.append("    style homeauto fill:#7F77DD,color:#fff")

    return "\n".join(lines)


def generate_vlan_diagram():
    """Generate a Mermaid diagram of the VLAN topology."""
    return """graph TD
    ISP[\"🌐 ISP / WAN\"] --> FW

    subgraph firewall[\"OPNsense Firewall\"]
        FW[\"Glovary i3-N355\n6x 2.5GbE\"]
    end

    FW --> SW

    subgraph switch[\"MokerLink 8-port PoE\"]
        SW[\"Managed Switch\n10.0.10.2\"]
    end

    SW --> |\"VLAN 10 MGMT\"| AMDPVE[\"AMDPVE\n10.0.10.10\"]
    SW --> |\"VLAN 10 MGMT\"| N1PVE[\"N1 Mini PVE\n10.0.10.11\"]
    SW --> |\"VLAN 10 MGMT\"| ZIMA[\"ZimaBoard NAS\n10.0.10.40\"]
    SW --> |\"VLAN 10 MGMT\"| PI4[\"Pi 4 k3s-cp\n10.0.10.30\"]
    SW --> |\"VLAN 10 MGMT\"| PI5[\"Pi 5 k3s-w1\n10.0.10.31\"]
    SW --> |\"VLAN 10 MGMT\"| WS[\"Workstation\n10.0.10.20\"]

    AMDPVE --> |\"VLAN 40\"| SEC[\"Security Stack VMs\n10.0.40.x\"]
    AMDPVE --> |\"VLAN 61\"| RED[\"Red Team VM\n10.0.61.x\"]
    AMDPVE --> |\"VLAN 62\"| PURPLE[\"Purple Team VMs\n10.0.62.x\"]
    AMDPVE --> |\"VLAN 20\"| K3SW_AMD[\"k3s worker\n10.0.20.12\"]

    N1PVE --> |\"VLAN 20\"| K3SW_N1[\"k3s worker\n10.0.20.13\"]
    N1PVE --> |\"VLAN 10\"| GITEA[\"Gitea LXC\n10.0.10.50\"]

    PI4 --> |\"VLAN 20\"| K3S_CP[\"k3s control plane\n10.0.20.10\"]
    PI5 --> |\"VLAN 20\"| K3SW_PI5[\"k3s worker\n10.0.20.11\"]

    style firewall fill:#A32D2D,color:#fff
    style switch fill:#0C447C,color:#fff
    style SEC fill:#A32D2D,color:#fff
    style RED fill:#712B13,color:#fff
    style PURPLE fill:#3C3489,color:#fff"""


def write_diagram_page():
    """Write the generated diagrams to a docs page."""
    output_path = DOCS_DIR / "diagrams.md"
    service_graph = generate_service_graph()
    vlan_diagram = generate_vlan_diagram()

    content = f"""# Infrastructure Diagrams

*Auto-generated from k3s manifests and network config. Do not edit manually.*

## Service Graph

```mermaid
{service_graph}
```

## VLAN Topology

```mermaid
{vlan_diagram}
```
"""
    output_path.write_text(content)
    print(f"✓ Written: {output_path}")


if __name__ == "__main__":
    print("Generating architecture diagrams...")
    DOCS_DIR.mkdir(exist_ok=True)
    write_diagram_page()
    print("Done.")
