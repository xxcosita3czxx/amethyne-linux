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
    amethyne-gtk-theme
    bibata-cursor-theme-bin
    amethyne-notification-daemon
    hyprland
    hyprpaper
    xdg-desktop-portal-hyprland
    waybar
    fuzzel
    kitty
    sddm
)

_DRIVERS=(
    mesa
    libglvnd
    libva-mesa-driver
    vulkan-intel
    vulkan-radeon
    vulkan-nouveau
    intel-media-driver
    xf86-video-amdgpu
    xf86-video-intel
    xf86-video-nouveau
    qemu-guest-agent
    spice-vdagent
    vulkan-virtio
    virglrenderer
)

_DEV_PACKAGES=(
    gtk3-demos
    gtk4-demos
    themix-full-git
)

# Packages shared by the live ISO and the installed system.
BASE_PACKAGES=(
    base
    chaotic-keyring
    chaotic-mirrorlist
    linux-zen
    linux-firmware
    "${_DRIVERS[@]}"
    networkmanager
    libnotify
    sudo
    nano
    less
    "${_UI_PACKAGES[@]}"
    "${_DEV_PACKAGES[@]}"
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
INSTALL_PACKAGES=()

PACMAN_CONF=$(cat <<'EOF'
[options]
ILoveCandy
HoldPkg     = pacman glibc
Architecture = auto
CheckSpace
ParallelDownloads = 5
SigLevel = Required DatabaseOptional
LocalFileSigLevel = Optional

[core]
Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch

[extra]
Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch

[chaotic-aur]
Include = /etc/pacman.d/chaotic-mirrorlist
EOF
)
