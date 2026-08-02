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
