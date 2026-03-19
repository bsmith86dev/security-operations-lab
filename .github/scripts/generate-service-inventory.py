#!/usr/bin/env python3
"""
.github/scripts/generate-service-inventory.py
Generates a service inventory markdown page from k3s manifests.
Called by 04-docs.yml before MkDocs build.
Produces docs/service-inventory.md
"""

import yaml
from pathlib import Path
from datetime import datetime

DOCS_DIR = Path("docs")
K3S_DIR = Path("k3s")

EXTERNAL_URLS = {
    "nextcloud":     "https://nextcloud.blerdmh.com",
    "jellyfin":      "https://jellyfin.blerdmh.com",
    "homeassistant": "https://ha.blerdmh.com",
    "grafana":       "https://grafana.blerdmh.com",
    "cloudflared":   "https://dash.cloudflare.com (tunnel)",
}

INTERNAL_URLS = {
    "prometheus":  "http://prometheus.monitoring.svc:9090",
    "loki":        "http://loki.monitoring.svc:3100",
    "radarr":      "http://radarr.media.svc:7878",
    "sonarr":      "http://sonarr.media.svc:8989",
    "lidarr":      "http://lidarr.media.svc:8686",
}

GPU_WORKLOADS = {"jellyfin"}
ARM_WORKLOADS  = {"nextcloud", "homeassistant"}


def load_yaml_multi(path):
    docs = []
    try:
        with open(path) as f:
            for doc in yaml.safe_load_all(f):
                if doc:
                    docs.append(doc)
    except Exception:
        pass
    return docs


def collect_services():
    services = []
    for yml in K3S_DIR.rglob("*.yml"):
        if any(x in yml.name for x in ["sealed", "values", "network-policy", "namespace"]):
            continue
        for doc in load_yaml_multi(yml):
            if doc.get("kind") != "Deployment":
                continue
            name      = doc["metadata"].get("name", "")
            namespace = doc["metadata"].get("namespace", "")
            spec      = doc.get("spec", {}).get("template", {}).get("spec", {})
            containers = spec.get("containers", [])
            if not containers:
                continue
            c         = containers[0]
            image     = c.get("image", "unknown")
            resources = c.get("resources", {})
            req       = resources.get("requests", {})
            lim       = resources.get("limits", {})
            has_gpu   = "amd.com/gpu" in req

            services.append({
                "name":      name,
                "namespace": namespace,
                "image":     image,
                "cpu_req":   req.get("cpu", "—"),
                "mem_req":   req.get("memory", "—"),
                "cpu_lim":   lim.get("cpu", "—"),
                "mem_lim":   lim.get("memory", "—"),
                "gpu":       has_gpu,
                "external":  EXTERNAL_URLS.get(name, ""),
                "internal":  INTERNAL_URLS.get(name, ""),
                "node":      "k3s-worker-amd (GPU)" if has_gpu
                             else ("Pi 5" if name in ARM_WORKLOADS else "any"),
            })
    return sorted(services, key=lambda x: (x["namespace"], x["name"]))


def format_url(url):
    if not url:
        return "internal only"
    if url.startswith("http"):
        label = url.replace("https://", "").replace("http://", "").split("/")[0]
        return f"[{label}]({url})"
    return url


def write_inventory(services):
    lines = [
        "# Service Inventory",
        "",
        f"*Auto-generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} "
        f"from k3s manifests. Do not edit manually.*",
        "",
        f"**Total services:** {len(services)}",
        "",
        "## All Services",
        "",
        "| Service | Namespace | Image | CPU req/lim | RAM req/lim | Node | External URL |",
        "|---------|-----------|-------|-------------|-------------|------|-------------|",
    ]

    for s in services:
        gpu_badge = " 🎮" if s["gpu"] else ""
        lines.append(
            f"| **{s['name']}**{gpu_badge} "
            f"| `{s['namespace']}` "
            f"| `{s['image'].split('/')[-1]}` "
            f"| {s['cpu_req']} / {s['cpu_lim']} "
            f"| {s['mem_req']} / {s['mem_lim']} "
            f"| {s['node']} "
            f"| {format_url(s['external'])} |"
        )

    lines += [
        "",
        "🎮 = AMD GPU accelerated (RX 5700 XT via VAAPI)",
        "",
        "## By Namespace",
        "",
    ]

    by_ns = {}
    for s in services:
        by_ns.setdefault(s["namespace"], []).append(s)

    for ns, svcs in sorted(by_ns.items()):
        lines.append(f"### `{ns}`")
        lines.append("")
        for s in svcs:
            ext = f" → {format_url(s['external'])}" if s["external"] else ""
            lines.append(f"- **{s['name']}**{ext}")
        lines.append("")

    output = DOCS_DIR / "service-inventory.md"
    output.write_text("\n".join(lines))
    print(f"✓ Written: {output} ({len(services)} services)")


if __name__ == "__main__":
    print("Generating service inventory...")
    DOCS_DIR.mkdir(exist_ok=True)
    services = collect_services()
    write_inventory(services)
    print("Done.")
