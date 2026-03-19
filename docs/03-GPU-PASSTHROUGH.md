# GPU Passthrough — RX 5700 XT to k3s-worker-amd VM
# Host: AMDPVE (Ryzen 9 7900X) | GPU: AMD RX 5700 XT 10GB
# Guest: k3s-worker-amd VM (VMID 110)

## Overview
We pass the RX 5700 XT directly to the k3s-worker-amd VM using PCIe passthrough.
Jellyfin runs as a k3s pod on that worker, requests the GPU as a device,
and uses VAAPI (VA-API) for hardware transcoding.

AMD RX 5700 XT supports via VAAPI:
  - H.264 encode/decode
  - HEVC (H.265) encode/decode
  - VP9 decode
  - AV1 decode (driver dependent)

---

## Step 1 — Enable IOMMU on AMDPVE Host

### 1.1 Edit GRUB bootloader

```bash
# SSH into AMDPVE as root
ssh root@10.0.10.10

# Edit GRUB config
nano /etc/default/grub

# Find this line:
GRUB_CMDLINE_LINUX_DEFAULT="quiet"

# Replace with (AMD CPU — use amd_iommu):
GRUB_CMDLINE_LINUX_DEFAULT="quiet amd_iommu=on iommu=pt"

# Save and update GRUB
update-grub
```

### 1.2 Load VFIO kernel modules

```bash
# Add modules that must load at boot
cat >> /etc/modules << 'EOF'
vfio
vfio_iommu_type1
vfio_pci
vfio_virqfd
EOF
```

### 1.3 Blacklist AMD GPU drivers on the HOST
# The host must NOT claim the GPU — VFIO claims it instead

```bash
cat > /etc/modprobe.d/blacklist-amd-gpu.conf << 'EOF'
# Blacklist AMD GPU drivers so VFIO can claim the RX 5700 XT
blacklist amdgpu
blacklist radeon
EOF
```

### 1.4 Find the GPU PCI address and vendor/device IDs

```bash
# Reboot first to load IOMMU
reboot

# After reboot, find the RX 5700 XT
lspci | grep -i amd | grep -i vga
# Example output:
# 01:00.0 VGA compatible controller: Advanced Micro Devices [AMD/ATI] Navi 10 [Radeon RX 5600 OEM/5700/5700 XT]
# 01:00.1 Audio device: Advanced Micro Devices [AMD/ATI] Navi 10 HDMI Audio

# Note BOTH PCI IDs — GPU and its audio device must pass together
# In this example: 01:00.0 and 01:00.1

# Get vendor:device IDs
lspci -n -s 01:00
# Example:
# 01:00.0 0300: 1002:731f (rev ca)   ← GPU
# 01:00.1 0403: 1002:ab38             ← Audio

# Verify IOMMU grouping — GPU and audio MUST be in same group
find /sys/kernel/iommu_groups/ -type l | sort | xargs ls -la | grep "01:00"
```

### 1.5 Bind VFIO to the GPU

```bash
# Using the vendor:device IDs from above (1002:731f and 1002:ab38)
cat > /etc/modprobe.d/vfio.conf << 'EOF'
# Bind RX 5700 XT (GPU + audio) to VFIO
# Replace IDs if your output differs
options vfio-pci ids=1002:731f,1002:ab38
EOF

# Update initramfs
update-initramfs -u

# Reboot
reboot

# Verify VFIO claimed the GPU (not amdgpu)
lspci -nnk | grep -A 3 "01:00.0"
# Should show: Kernel driver in use: vfio-pci
```

---

## Step 2 — Configure k3s-worker-amd VM for GPU Passthrough

### 2.1 Add GPU to VM in Proxmox

```bash
# Stop the VM first if running
qm stop 110

# Add PCIe passthrough device
# Replace 01:00 with your actual PCI address
qm set 110 -hostpci0 01:00,allFunctions=1,pcie=1,x-vga=0

# allFunctions=1 passes both GPU (01:00.0) and audio (01:00.1)
# pcie=1 uses PCIe instead of PCI (required for modern GPUs)
# x-vga=0 keeps it as a compute/passthrough device (not primary display)

# Also set machine type to q35 (required for PCIe passthrough)
qm set 110 --machine q35
qm set 110 --bios ovmf  # UEFI required for q35

# Add EFI disk for UEFI boot
qm set 110 --efidisk0 local-lvm:1,efitype=4m,pre-enrolled-keys=0

# Start VM
qm start 110
```

### 2.2 Verify GPU is visible inside the VM

```bash
# SSH into k3s-worker-amd
ssh labadmin@10.0.20.12

# Check GPU is present
lspci | grep -i amd
# Should show the RX 5700 XT

# Install AMD GPU driver and VAAPI libraries
sudo apt update
sudo apt install -y \
  linux-firmware \
  libva2 \
  libva-drm2 \
  vainfo \
  mesa-va-drivers \
  mesa-vulkan-drivers \
  libdrm-amdgpu1

# Verify VAAPI works
vainfo
# Should show supported profiles including H264, HEVC
# Example:
# VAProfileH264Main               : VAEntrypointVLD
# VAProfileHEVCMain               : VAEntrypointVLD
# VAProfileHEVCMain10             : VAEntrypointVLD

# Check render device exists
ls -la /dev/dri/
# Should show: renderD128 (or similar)
```

---

## Step 3 — Install AMD GPU Device Plugin for k3s

The k8s-device-plugin from AMD makes the GPU schedulable as a k3s resource.
Pods can then request `amd.com/gpu: 1` in their resource spec.

```bash
# On k3s control plane (Pi 4)
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Deploy AMD GPU device plugin as DaemonSet
# It only runs on nodes where the GPU is present (node selector)
kubectl apply -f https://raw.githubusercontent.com/RadeonOpenCompute/k8s-device-plugin/master/k8s-ds-amdgpu-dp.yaml

# Label the worker node so the device plugin targets it
kubectl label node k3s-worker-amd amd.com/gpu=present

# Verify plugin is running on the correct node
kubectl get pods -n kube-system | grep amdgpu

# Verify GPU is allocatable
kubectl describe node k3s-worker-amd | grep -A 10 "Allocatable"
# Should show:
# amd.com/gpu: 1
```

---

## Step 4 — Update Ansible for Worker VM GPU Setup

Add to `ansible/roles/k3s/tasks/worker.yml` for k3s-worker-amd specifically:

```yaml
- name: Install VAAPI and AMD GPU libraries (GPU worker only)
  apt:
    name:
      - linux-firmware
      - libva2
      - libva-drm2
      - vainfo
      - mesa-va-drivers
      - mesa-vulkan-drivers
      - libdrm-amdgpu1
    state: present
  when: inventory_hostname == 'k3s-worker-amd'

- name: Add labadmin to render and video groups
  user:
    name: labadmin
    groups: render,video
    append: yes
  when: inventory_hostname == 'k3s-worker-amd'
```

---

## Troubleshooting

### GPU not showing in VM
```bash
# Check IOMMU groups — if GPU shares a group with other devices
# you may need to pass ALL devices in that group
find /sys/kernel/iommu_groups/ -type l | sort | \
  awk -F/ '{print $5, $NF}' | sort -n | grep -A 5 -B 5 "0000:01:00"

# If other critical devices share the group, use ACS override patch
# (advanced — only if needed)
```

### VAAPI not working in VM
```bash
# Confirm render group membership
groups labadmin  # Should include 'render' and 'video'

# Check device permissions
ls -la /dev/dri/renderD128
# Should be: crw-rw---- root render

# Force correct permissions
sudo chmod 660 /dev/dri/renderD128
sudo chown root:render /dev/dri/renderD128
```

### Jellyfin pod not scheduling on GPU node
```bash
# Check node has GPU resource
kubectl describe node k3s-worker-amd | grep amd.com/gpu

# Check pod events
kubectl describe pod -n media -l app=jellyfin | grep -A 10 Events
```
