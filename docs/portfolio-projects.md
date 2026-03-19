# Portfolio Projects

Five cybersecurity projects built on this lab, structured for GitHub and resume use.
Each project has a dedicated repo, architecture writeup, and documented deliverables.

---

## Project 1 — Detection Engineering Lab

**Objective:** Build and tune custom detection rules mapped to MITRE ATT&CK.
Demonstrate detection engineering skills — the #1 hiring priority for SOC L2/L3.

**What you build:**

- Run Caldera adversary emulation against VLAN 62 (Purple Team) targets
- Write Sigma rules that detect each ATT&CK technique
- Import rules into Wazuh and validate they fire on real attack traffic
- Build an ATT&CK Navigator heatmap showing your detection coverage

**Lab components used:** AMDPVE → Wazuh (VLAN 40), Caldera (VLAN 61), Windows AD (VLAN 62)

**Deliverables:**

- GitHub repo: `blerdmh-detection-engineering`
- `/sigma-rules/` — custom rules per ATT&CK technique
- `/navigator/` — ATT&CK Navigator coverage layer JSON
- `/reports/` — incident writeups for each simulated attack
- `README.md` — methodology, tools, and lessons learned

**Resume bullet:**
> Developed 15+ custom Sigma detection rules mapped to MITRE ATT&CK covering credential access, lateral movement, and exfiltration techniques; validated against live adversary emulation using Caldera in an isolated purple team environment.

---

## Project 2 — Honeypot Threat Intelligence Pipeline

**Objective:** Collect real threat data, analyze TTPs, and automate IOC-based firewall blocking.

**What you build:**

- Deploy T-Pot or OpenCanary on VLAN 50 (IoT/Honeypot)
- Ship honeypot alerts to MISP threat intelligence platform
- Build an automated pipeline: MISP IOC → OPNsense firewall rule
- Generate a 30-day threat report from collected data

**Lab components used:** VLAN 50 honeypot VM, MISP (VLAN 40), OPNsense API, Wazuh

**Deliverables:**

- GitHub repo: `blerdmh-threat-intel-pipeline`
- `/pipeline/` — Python automation scripts (MISP API → OPNsense API)
- `/reports/30-day-threat-report.md` — attacker TTPs, top source IPs, techniques observed
- Architecture diagram showing data flow
- `README.md` — full pipeline walkthrough

**Resume bullet:**
> Built an automated threat intelligence pipeline collecting IOCs from a production honeypot, ingesting into MISP, and triggering real-time OPNsense firewall blocks — reducing mean time to block from manual to under 60 seconds.

---

## Project 3 — Active Directory Attack & Defense

**Objective:** Document the full AD kill chain with corresponding Wazuh detections for each stage.

**What you build:**

- Deploy Windows Server 2022 AD DC + 2 workstation VMs on VLAN 62
- Execute full kill chain from Kali (VLAN 61): enumeration → Kerberoasting → pass-the-hash → DCSync
- Wazuh + Sysmon detects each stage in real time
- Write detection rules and tuning notes for each technique

**Lab components used:** Kali VM (VLAN 61), Windows AD (VLAN 62), Wazuh (VLAN 40)

**Kill chain stages documented:**

1. Network enumeration (Nmap, BloodHound)
2. AS-REP roasting (Rubeus)
3. Kerberoasting (Impacket)
4. Pass-the-hash (CrackMapExec)
5. DCSync (Mimikatz / Impacket secretsdump)
6. Persistence (Golden ticket)

**Deliverables:**

- GitHub repo: `blerdmh-ad-attack-defense`
- `/attack-playbook/` — step-by-step attack commands with screenshots
- `/detections/` — Wazuh rules + Sysmon config for each technique
- `/reports/` — Purple team exercise report
- `README.md` — methodology and architecture

**Resume bullet:**
> Executed and documented a complete Active Directory attack chain (enumeration through DCSync) in an isolated purple team lab; developed corresponding Wazuh + Sysmon detection rules that reduced false negatives by tuning against real attack telemetry.

---

## Project 4 — IoT Security Assessment

**Objective:** Perform a professional security assessment of lab IoT devices (ESP32, M5Stack).

**What you build:**

- Capture and analyze ESP32 firmware
- Capture all network traffic from VLAN 50 (Zeek + Wireshark)
- Test authentication, encryption, and update mechanism security
- Use Hak5 Pineapple to test WiFi security of IoT devices
- Write a professional pentest report

**Lab components used:** ESP32/M5Stack devices (VLAN 50), Zeek (VLAN 40), Hak5 Pineapple, Raspberry Pi 0

**Deliverables:**

- GitHub repo: `blerdmh-iot-security-assessment`
- `/report/pentest-report.pdf` — full professional format (executive summary, findings, CVSS scores, remediation)
- `/firmware-analysis/` — Binwalk/Ghidra notes
- `/pcaps/` — anonymized Zeek logs showing device behavior
- `README.md` — methodology

**Resume bullet:**
> Conducted a full security assessment of IoT devices including firmware analysis, network traffic baseline, authentication testing, and wireless security review; delivered findings in a professional penetration testing report format with CVSS-scored vulnerabilities.

---

## Project 5 — SOAR Automation Pipeline

**Objective:** Build and document a security automation pipeline that reduces analyst toil.

**What you build:**

- Deploy Shuffle SOAR on VLAN 40
- Build workflow: Wazuh alert fires → Shuffle → enrich IOC via VirusTotal API → create TheHive case → post Discord/Slack alert
- Build second workflow: failed SSH login → auto-block in OPNsense → notify
- Document all workflows with exported configs

**Lab components used:** Wazuh (VLAN 40), Shuffle SOAR (VLAN 40), TheHive (VLAN 40), OPNsense API

**Deliverables:**

- GitHub repo: `blerdmh-soar-automation`
- `/workflows/` — Shuffle workflow exports (JSON)
- `/docs/` — workflow documentation with screenshots
- Demo video (screen recording) of end-to-end alert → case → notification
- `README.md` — automation philosophy and design decisions

**Resume bullet:**
> Designed and implemented a SOAR automation pipeline integrating Wazuh, Shuffle, TheHive, and OPNsense; automated IOC enrichment via VirusTotal API and SSH brute-force auto-blocking, reducing mean time to respond from 15 minutes to under 90 seconds.

---

## Interview Talking Points

For any of these projects, be prepared to discuss:

- **Why you chose the tools you did** — know one alternative for each tool
- **What didn't work** — interviewers value honesty about troubleshooting
- **What you'd do differently** — shows engineering maturity
- **How this maps to enterprise** — "In a real SOC, this would be replaced by X"
- **What you detected vs what you missed** — detection gaps are as important as coverage
