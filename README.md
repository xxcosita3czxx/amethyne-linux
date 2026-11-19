# Amethyne Linux

## Build ISO

Build the default preset:

```bash
./build.sh
```

Local Amethyne packages under `packages/` are built automatically if their expected package artifact is missing. They are collected into a temporary pacman repository and installed into the ISO through `mkarchiso`.

Force local package rebuilds before the ISO build:

```bash
./build.sh --rebuild-packages
```

Set package version/release used for local packages:

```bash
./build.sh --package-version 0.2.0 --package-rel 1 --rebuild-packages
```

## Development package repo

Build/collect local packages into a pacman repository and serve it over HTTP:

```bash
./build.sh --repo
```

Force rebuild all local packages before serving:

```bash
./build.sh --repo --rebuild-packages
```

Rebuild and serve only one package:

```bash
./build.sh --repo --rebuild-packages --package amethyne-desktop
```

You can pass `--package` more than once to include multiple packages.

Serve the dev repo and automatically refresh it when package source files change:

```bash
./build.sh --repo --watch --package amethyne-desktop
```

The watcher checks package sources every second by default. Build output directories (`build/`, `dist/`, `packages/`) are ignored.

Use a custom bind address or port:

```bash
./build.sh --repo --repo-port 8081
```

For a libvirt/virt-manager NAT guest, add this above `[core]`/`[extra]` in `/etc/pacman.conf` inside the VM:

```ini
[amethyne-dev]
SigLevel = Optional TrustAll
Server = http://192.168.122.1:8080
```

Then update packages inside the VM without rebuilding the ISO:

```bash
sudo pacman -Sy amethyne-desktop
```

In repo mode, package rebuilds automatically bump the Arch package release suffix while keeping the version you set:

```text
0.1.0-1
0.1.0-2
0.1.0-3
```

So this is usually enough during development:

```bash
./build.sh --repo --rebuild-packages
```

Set real package versions independently in each package's `package.toml`:

```toml
[package]
name = "amethyne-desktop"
version = "0.2.0"
```

You can still override every local package version for one build if needed:

```bash
./build.sh --repo --rebuild-packages --package-version 0.2.0
```

You can still override the package release manually when needed:

```bash
./build.sh --repo --rebuild-packages --package-rel 42
```

## Package builder

Python app packages are built through the shared root builder:

```bash
./package-builder.py amethyne-settings --clean
./package-builder.py amethyne-notification-daemon --clean
```

Each package keeps its own metadata and Arch package template in:

```text
packages/<package>/package.toml
packages/<package>/PKGBUILD.in
```

The generated package is written to:

```text
packages/<package>/packages/
```

See [`docs/packages.md`](docs/packages.md) for the package syntax and template format.

## Installer data

The ISO exports package lists, generated pacman config, and the preset airootfs overlay under:

```text
/usr/share/amethyne/installer/
```

See [`docs/installer.md`](docs/installer.md) for details.
