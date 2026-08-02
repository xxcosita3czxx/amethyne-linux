#!/usr/bin/env bash

iso_name="%ISO_NAME%"
iso_label="%ISO_LABEL%"
iso_publisher="%ISO_PUBLISHER%"
iso_application="%ISO_APPLICATION%"
iso_version="%ISO_VERSION%"
install_dir="%INSTALL_DIR%"
buildmodes=('iso')
bootmodes=(
  'bios.syslinux'
  'uefi.grub'
)
arch="%ARCH%"
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'xz')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
)
