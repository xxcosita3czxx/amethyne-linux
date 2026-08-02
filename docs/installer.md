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
install.<arch>
```

For the current x86_64 preset:

```text
base.x86_64
live.x86_64
install.x86_64
```

Meanings:

| File | Contents |
| --- | --- |
| `base.<arch>` | `BASE_PACKAGES` from the preset. Shared baseline packages. |
| `live.<arch>` | `LIVE_PACKAGES` from the preset. Packages only needed in the live ISO. |
| `install.<arch>` | `INSTALL_PACKAGES` from the preset. Packages only intended for an installed target system. |

The installer can combine these lists as needed. For example, a target install would usually use `base.<arch> + install.<arch>`, while the live ISO package set is `base.<arch> + live.<arch>`.

## Pacman config and local package repo

The generated pacman config is copied to:

```text
/usr/share/amethyne/installer/pacman.conf
```

This includes the normal preset repositories and the local Amethyne package repository.

The built local package repository is exported into the live system at:

```text
/usr/share/amethyne/installer/repo/
```

That directory contains the custom Amethyne `.pkg.tar.*` files plus the pacman repo database for `amethyne-local`.

During the ISO build, the live image uses a build-time repo path like:

```text
file:///work/.build/<preset>/package-repo
```

For installer runtime data, that path is rewritten in `pacman.conf` to:

```text
file:///usr/share/amethyne/installer/repo
```

This lets the future installer install Amethyne custom packages from the ISO instead of trying to recover package files from the already-installed live root.

## Airootfs overlay

The source preset `airootfs` overlay is copied into the live system at:

```text
/usr/share/amethyne/installer/airootfs/
```

This overlay is intended to describe reusable base/target filesystem defaults for Amethyne. Live-ISO-only files should not live here; they should be provided by the `amethyne-live` package instead.

Example:

```text
/usr/share/amethyne/installer/airootfs/etc/skel/
/usr/share/amethyne/installer/airootfs/etc/systemd/system/
```

The installer can use this directory as a target-root overlay source. Live-only behavior such as archiso initramfs presets, live user setup, live autologin, live MOTD, and firstboot masking belongs in `amethyne-live`.
