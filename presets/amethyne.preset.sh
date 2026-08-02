#!/usr/bin/env bash

ISO_NAME="amethyne-linux"
ISO_LABEL="AMETHYNE"
ISO_PUBLISHER="Amethyne Linux"
ISO_APPLICATION="Amethyne Linux Live ISO"
ISO_VERSION="$(date +%Y.%m.%d)"

INSTALL_DIR="amethyne"
ARCH="x86_64"

KERNEL_IMAGE="vmlinuz-linux-zen"
INITRAMFS_IMAGE="initramfs-linux-zen.img"

_UI_PACKAGES=(
    amethyne-desktop
    amethyne-settings
    amethyne-notification-daemon
    hyprland
    hyprpaper
    xdg-desktop-portal-hyprland
    waybar
    kitty
    sddm
)

_DRIVERS=(
    mesa
    libglvnd
    vulkan-virtio
    virglrenderer
)

# Packages shared by the live ISO and the installed system.
BASE_PACKAGES=(
    base
    linux-zen
    linux-firmware
    "${_DRIVERS[@]}"
    networkmanager
    libnotify
    sudo
    nano
    "${_UI_PACKAGES[@]}"
)

# Packages only needed in the live ISO.
LIVE_PACKAGES=(
    # Required by archiso to build a bootable live initramfs.
    mkinitcpio-archiso
    # Required by archiso's BIOS Syslinux boot mode.
    syslinux
    # amethyne specific
    amethyne-installer
    amethyne-live
)

# Packages only intended for the installed system.
# The ISO builder does not consume this yet; your future installer can combine
# BASE_PACKAGES + INSTALL_PACKAGES for the target system.
INSTALL_PACKAGES=()

PACMAN_CONF=$(cat <<'EOF'
[options]
HoldPkg     = pacman glibc
Architecture = auto
CheckSpace
ParallelDownloads = 5
SigLevel = Required DatabaseOptional
LocalFileSigLevel = Optional

[core]
Include = /etc/pacman.d/mirrorlist

[extra]
Include = /etc/pacman.d/mirrorlist
EOF
)
