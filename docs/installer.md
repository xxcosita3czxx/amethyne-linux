# Installer runtime data

The ISO build exports preset data into the live system for the future Amethyne installer.

At runtime, the installer can read:

```text
/usr/share/amethyne/installer/
```

## Package lists

Generated package lists are stored under:

```text
/usr/share/amethyne/installer/packages/
```

Files:

```text
base.<arch>
live.<arch>
live-only.<arch>
target.<arch>
install-only.<arch>
```

For the current x86_64 preset:

```text
base.x86_64
live.x86_64
live-only.x86_64
target.x86_64
install-only.x86_64
```

Meanings:

| File | Contents |
| --- | --- |
| `base.<arch>` | `BASE_PACKAGES` from the preset. Shared baseline packages. |
| `live-only.<arch>` | `LIVE_PACKAGES` from the preset. Packages only needed in the live ISO. |
| `install-only.<arch>` | `INSTALL_PACKAGES` from the preset. Packages only intended for an installed target system. |
| `live.<arch>` | `BASE_PACKAGES + LIVE_PACKAGES`. This is what the live ISO uses. |
| `target.<arch>` | `BASE_PACKAGES + INSTALL_PACKAGES`. This is the starting package list for installing Amethyne to disk. |

The installer should normally use:

```text
/usr/share/amethyne/installer/packages/target.x86_64
```

as the target system package list.

## Pacman config

The generated pacman config is copied to:

```text
/usr/share/amethyne/installer/pacman.conf
```

This includes the normal preset repositories and the temporary local Amethyne package repository used by the live build.

Important: the generated local repository path is build-time oriented:

```text
file:///work/.build/<preset>/package-repo
```

For a real installer, this may need to be rewritten or replaced with a target install repository source. Treat this file as a useful starting point rather than a final target-system config.

## Airootfs overlay

The source preset `airootfs` overlay is copied into the live system at:

```text
/usr/share/amethyne/installer/airootfs/
```

This lets the installer inspect or reuse files from the live image overlay when creating an installed system.

Example:

```text
/usr/share/amethyne/installer/airootfs/etc/skel/
/usr/share/amethyne/installer/airootfs/etc/systemd/system/
/usr/share/amethyne/installer/airootfs/root/customize_airootfs.sh
```

Be careful when applying the airootfs overlay to a target installation. Some files are live-ISO-specific, such as autologin, live user setup, or build-time customization scripts. The installer should copy only the parts that make sense for an installed system, or use a future dedicated target-root overlay.
