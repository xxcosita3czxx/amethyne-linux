# Amethyne package format

Amethyne Python app packages live under:

```text
packages/<package-name>/
```

Each package is built by the shared root builder:

```bash
./package-builder.py <package-name> --clean
```

The package directory contains app source files plus two packaging files:

```text
packages/<package-name>/package.toml
packages/<package-name>/PKGBUILD.in
```

## Directory layout

Typical package layout:

```text
packages/example-app/
├── main.py
├── style.gtk.css
├── package.toml
└── PKGBUILD.in
```

Packages with more source files can add normal Python modules/directories:

```text
packages/example-app/
├── main.py
├── components/
├── pages/
├── style.gtk.css
├── package.toml
└── PKGBUILD.in
```

Generated build output is placed inside the package directory:

```text
packages/<package-name>/build/
packages/<package-name>/dist/
packages/<package-name>/packages/
```

The final pacman package is written to:

```text
packages/<package-name>/packages/
```

## ISO integration

`./build.sh` automatically discovers all package directories containing `package.toml`.

During an ISO build, `scripts/container-build.sh`:

1. Builds each local package if the expected `.pkg.tar.*` artifact is missing.
2. Rebuilds all local packages when `./build.sh --rebuild-packages` is used.
3. Copies package artifacts into a temporary repository under:

   ```text
   .build/<preset>/package-repo/
   ```

4. Runs `repo-add` to generate the repository database.
5. Appends this repository to the generated archiso `pacman.conf`.
6. Lets pacman resolve local package names from that repo when the preset lists them in `BASE_PACKAGES` or `LIVE_PACKAGES`.

The preset remains the source of truth for what gets installed. The build script creates the local repository, but it does not automatically append local package names to `packages.<arch>`.

Force rebuild local packages while building the ISO:

```bash
./build.sh --rebuild-packages
```

Set the local package version/release used by the ISO build:

```bash
./build.sh --package-version 0.2.0 --package-rel 1 --rebuild-packages
```

## Package build command

From the repository root:

```bash
./package-builder.py amethyne-settings --clean
./package-builder.py amethyne-notification-daemon --clean
```

Useful flags:

```bash
./package-builder.py <package> --version 0.2.0
./package-builder.py <package> --pkgrel 2
./package-builder.py <package> --clean
./package-builder.py <package> --direct
```

`--direct` skips `makepkg` and writes a `.pkg.tar.zst` directly. This is useful on non-Arch hosts, but `makepkg` is preferred on Arch-like systems.

## `package.toml`

`package.toml` describes the app, PyInstaller inputs, runtime dependencies, and optional desktop entry.

### Full example

```toml
[package]
name = "example-app"
type = "python-app"
app_name = "example-app"
description = "Example application for Amethyne Linux"
url = "https://github.com/cosita3cz/amethyne-linux"
arch = "x86_64"
license = "custom"
entrypoint = "main.py"
dependencies = ["gtk4", "glib2", "python-gobject"]

[pyinstaller]
windowed = true
onefile = true
add_data = ["style.gtk.css:."]
collect_submodules = ["pages", "components"]
hidden_imports = [
  "gi",
  "gi.repository.Gtk",
  "gi.repository.Gio",
]

[desktop]
app_id = "cz.amethyne.ExampleApp"
name = "Example App"
generic_name = "Example"
comment = "Example desktop application"
icon = "application-x-executable"
terminal = false
categories = "Utility;GTK;"
startup_wm_class = "cz.amethyne.ExampleApp"
```

### `[package]`

Required unless noted:

| Key | Meaning |
| --- | --- |
| `name` | Pacman package name. Example: `amethyne-settings`. |
| `type` | Package build type. Optional; defaults to `python-app`. Use `stub` for metadata-only placeholder packages. |
| `app_name` | Installed executable name. Defaults to `name` if omitted. Not used by `stub` packages. |
| `description` | Package description used in `pkgdesc` and `.PKGINFO`. |
| `url` | Package/project URL. Optional; defaults to the Amethyne repo URL. |
| `arch` | Package architecture. Optional; defaults to `x86_64`. |
| `license` | Package license value. Optional; defaults to `custom`. |
| `entrypoint` | Python file passed to PyInstaller. Optional; defaults to `main.py`. |
| `dependencies` | Runtime pacman dependencies. |

Dependencies should use Arch package names because the produced package targets Amethyne/Arch.

Stub package example:

```toml
[package]
name = "amethyne-installer"
type = "stub"
description = "Installer placeholder package for Amethyne Linux"
url = "https://github.com/cosita3cz/amethyne-linux"
arch = "x86_64"
license = "custom"
dependencies = []
```

A `stub` package skips PyInstaller and produces a package containing only pacman metadata. This is useful for reserving package names before the real implementation exists.

Example:

```toml
dependencies = ["gtk4", "glib2", "gtk4-layer-shell", "python-gobject"]
```

### `[pyinstaller]`

Optional section. Controls PyInstaller arguments.

| Key | Meaning |
| --- | --- |
| `windowed` | If `true`, passes `--windowed`. Defaults to `true`. |
| `onefile` | If `true`, passes `--onefile`. Defaults to `true`. |
| `add_data` | List of `source:destination` values passed as `--add-data`. |
| `collect_submodules` | List passed as repeated `--collect-submodules`. |
| `hidden_imports` | List passed as repeated `--hidden-import`. |

Example:

```toml
[pyinstaller]
add_data = ["style.gtk.css:."]
collect_submodules = ["pages", "components"]
hidden_imports = ["gi", "gi.repository.Gtk"]
```

### `[desktop]`

Optional section. If present, the builder generates a `.desktop` file and installs it to:

```text
/usr/share/applications/<app_id>.desktop
```

| Key | Meaning |
| --- | --- |
| `app_id` | Desktop app ID and desktop filename stem. Required if `[desktop]` exists. |
| `name` | Display name. Required if `[desktop]` exists. |
| `generic_name` | Optional generic name. |
| `comment` | Optional app description. |
| `icon` | Icon name. Defaults to `application-x-executable`. |
| `terminal` | Whether the app launches in a terminal. Defaults to `false`. |
| `categories` | Desktop menu categories. Defaults to `Utility;`. |
| `startup_wm_class` | Optional startup/window class. |

Packages without a GUI launcher, such as background daemons, can omit `[desktop]`.

## Static file installs

Packages can install extra static files or whole directories using repeated `[[install]]` entries in `package.toml`.

Install one file:

```toml
[[install]]
source = "assets/default.png"
target = "/usr/share/backgrounds/amethyne/default.png"
mode = "0644"
```

Install a directory recursively:

```toml
[[install]]
source = "wallpapers"
target = "/usr/share/backgrounds/amethyne"
mode = "0644"
recursive = true
```

Fields:

| Key | Meaning |
| --- | --- |
| `source` | File or directory path relative to the package directory. |
| `target` | Absolute install path inside the target system/package root. |
| `mode` | File mode for installed files. Optional; defaults to `0644`. |
| `recursive` | If `true`, `source` must be a directory and all files are copied recursively. Defaults to `false`. |

If `recursive = false` and `source` is a directory, the builder creates only the `target` directory and ignores the source directory contents.

Recursive directory installs preserve the directory tree below `source`. The `target` path is the destination directory, not a parent that receives the source directory name.

For example:

```text
source: wallpapers
target: /usr/share/backgrounds/amethyne
```

with:

```text
wallpapers/default.png
wallpapers/dark/default.png
```

installs:

```text
/usr/share/backgrounds/amethyne/default.png
/usr/share/backgrounds/amethyne/dark/default.png
```

`[[install]]` works with `python-app`, `files`, and `stub` packages. A `stub` package with install entries is useful for static-content-only packages.

## `PKGBUILD.in`

Each package keeps a `PKGBUILD.in` template. The root builder renders this into a real `PKGBUILD` under:

```text
packages/<package>/build/makepkg/PKGBUILD
```

The template uses Python `string.Template` syntax: variables are written as `$name` or `${name}`.

Available variables:

| Variable | Meaning |
| --- | --- |
| `$pkgname` | Package name from `package.name`. |
| `$pkgver` | Version passed to `package-builder.py --version`. |
| `$pkgrel` | Release passed to `package-builder.py --pkgrel`. |
| `$pkgdesc` | Description from `package.description`. |
| `$arch` | Shell-quoted package arch array contents. |
| `$url` | Package URL. |
| `$license` | Shell-quoted license array contents. |
| `$depends` | Shell-quoted dependency array contents. |
| `$source` | Shell-quoted source array contents. |
| `$sha256sums` | Shell-quoted checksum array contents. Currently all `SKIP`. |
| `$app_name` | Installed executable/source binary name. |
| `$desktop_app_id` | Desktop app ID if `[desktop]` exists; otherwise empty. |
| `$static_install` | Generated install commands for `[[install]]` entries. Include this inside `package()`. |

### GUI app template example

```bash
pkgname=$pkgname
pkgver=$pkgver
pkgrel=$pkgrel
pkgdesc='$pkgdesc'
arch=($arch)
url='$url'
license=($license)
depends=($depends)
source=($source)
sha256sums=($sha256sums)

package() {
    install -Dm755 "$srcdir/$app_name" "$pkgdir/usr/bin/$app_name"
    install -Dm644 "$srcdir/$desktop_app_id.desktop" "$pkgdir/usr/share/applications/$desktop_app_id.desktop"
}
```

### Daemon/template without desktop file

```bash
pkgname=$pkgname
pkgver=$pkgver
pkgrel=$pkgrel
pkgdesc='$pkgdesc'
arch=($arch)
url='$url'
license=($license)
depends=($depends)
source=($source)
sha256sums=($sha256sums)

package() {
    install -Dm755 "$srcdir/$app_name" "$pkgdir/usr/bin/$app_name"
}
```

## Direct package mode

When `makepkg` is unavailable, or when `--direct` is passed, `package-builder.py` creates a `.pkg.tar.zst` itself.

Direct mode installs the same generated files into a package root:

```text
usr/bin/<app_name>
usr/share/applications/<app_id>.desktop  # only when [desktop] exists
.PKGINFO
```

Direct mode is intentionally minimal. If a package needs complex install logic, prefer using `makepkg` and express that logic in `PKGBUILD.in`.

## Adding a new package

1. Create the package directory:

   ```bash
   mkdir -p packages/my-app
   ```

2. Add app source, usually starting with:

   ```text
   packages/my-app/main.py
   ```

3. Add `package.toml`.

4. Add `PKGBUILD.in`.

5. Build it:

   ```bash
   ./package-builder.py my-app --clean
   ```

6. Check output:

   ```text
   packages/my-app/packages/
   ```

## Current packages

```text
packages/amethyne-settings/
packages/amethyne-notification-daemon/
```
