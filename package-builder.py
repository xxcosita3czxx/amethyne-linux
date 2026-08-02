#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from string import Template

import tomllib

ROOT = Path(__file__).resolve().parent
PACKAGES_DIR = ROOT / "packages"
DEFAULT_PACKAGER = "Amethyne Builder <noreply@localhost>"


@dataclass(frozen=True)
class DesktopConfig:
    app_id: str
    name: str
    generic_name: str
    comment: str
    icon: str
    categories: str
    terminal: bool
    startup_wm_class: str | None


@dataclass(frozen=True)
class InstallEntry:
    source: str
    target: str
    mode: str | None
    recursive: bool


@dataclass(frozen=True)
class PackageConfig:
    root: Path
    name: str
    package_type: str
    app_name: str
    description: str
    url: str
    arch: str
    license: str
    entrypoint: str
    dependencies: list[str]
    add_data: list[str]
    hidden_imports: list[str]
    collect_submodules: list[str]
    windowed: bool
    onefile: bool
    desktop: DesktopConfig | None
    install_entries: list[InstallEntry]

    @property
    def build_dir(self) -> Path:
        return self.root / "build"

    @property
    def dist_dir(self) -> Path:
        return self.root / "dist"

    @property
    def package_out_dir(self) -> Path:
        return self.root / "packages"

    @property
    def pkgroot(self) -> Path:
        return self.build_dir / "pkgroot"

    @property
    def dist_binary(self) -> Path:
        return self.dist_dir / self.app_name

    @property
    def spec_file(self) -> Path:
        return self.root / f"{self.app_name}.spec"

    @property
    def desktop_file(self) -> Path | None:
        if self.desktop is None:
            return None
        return self.build_dir / f"{self.desktop.app_id}.desktop"


def run(command: list[str], cwd: Path) -> None:
    print(f"+ {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def read_config(package_root: Path) -> PackageConfig:
    config_path = package_root / "package.toml"
    if not config_path.is_file():
        raise RuntimeError(f"Missing package config: {config_path}")

    with config_path.open("rb") as config_file:
        data = tomllib.load(config_file)

    package = data["package"]
    pyinstaller = data.get("pyinstaller", {})
    desktop_data = data.get("desktop")
    install_entries = [
        InstallEntry(
            source=entry["source"],
            target=entry["target"],
            mode=entry.get("mode"),
            recursive=bool(entry.get("recursive", False)),
        )
        for entry in data.get("install", [])
    ]

    desktop = None
    if desktop_data:
        desktop = DesktopConfig(
            app_id=desktop_data["app_id"],
            name=desktop_data["name"],
            generic_name=desktop_data.get("generic_name", ""),
            comment=desktop_data.get("comment", ""),
            icon=desktop_data.get("icon", "application-x-executable"),
            categories=desktop_data.get("categories", "Utility;"),
            terminal=bool(desktop_data.get("terminal", False)),
            startup_wm_class=desktop_data.get("startup_wm_class"),
        )

    return PackageConfig(
        root=package_root,
        name=package["name"],
        package_type=package.get("type", "python-app"),
        app_name=package.get("app_name", package["name"]),
        description=package["description"],
        url=package.get("url", "https://github.com/cosita3cz/amethyne-linux"),
        arch=package.get("arch", "x86_64"),
        license=package.get("license", "custom"),
        entrypoint=package.get("entrypoint", "main.py"),
        dependencies=list(package.get("dependencies", [])),
        add_data=list(pyinstaller.get("add_data", [])),
        hidden_imports=list(pyinstaller.get("hidden_imports", [])),
        collect_submodules=list(pyinstaller.get("collect_submodules", [])),
        windowed=bool(pyinstaller.get("windowed", True)),
        onefile=bool(pyinstaller.get("onefile", True)),
        desktop=desktop,
        install_entries=install_entries,
    )


def clean(config: PackageConfig) -> None:
    for path in (config.build_dir, config.dist_dir, config.spec_file):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def os_release_info() -> str:
    os_release = Path("/etc/os-release")
    if not os_release.is_file():
        return ""
    return os_release.read_text(encoding="utf-8", errors="replace").lower()


def is_arch_like_host() -> bool:
    release_info = os_release_info()
    return "id=arch" in release_info or "id_like=arch" in release_info


def pyinstaller_install_hint() -> str:
    release_info = os_release_info()
    if "debian" in release_info or "ubuntu" in release_info or "linuxmint" in release_info:
        return "Install it with `sudo apt install pyinstaller` or `pipx install pyinstaller`."
    return "Install it with your distro package manager or `pipx install pyinstaller`."


def is_stub_package(config: PackageConfig) -> bool:
    return config.package_type == "stub"


def has_binary(config: PackageConfig) -> bool:
    return config.package_type == "python-app"


def validate_pyinstaller_inputs(config: PackageConfig) -> None:
    entrypoint = config.root / config.entrypoint
    if not entrypoint.is_file():
        raise RuntimeError(f"Missing PyInstaller entrypoint: {entrypoint}")

    for add_data in config.add_data:
        source = add_data.split(":", 1)[0]
        if not (config.root / source).exists():
            raise RuntimeError(f"Missing PyInstaller data source: {config.root / source}")


def build_binary(config: PackageConfig) -> None:
    validate_pyinstaller_inputs(config)

    pyinstaller = shutil.which("pyinstaller")
    if pyinstaller is None:
        raise RuntimeError(f"PyInstaller is not installed. {pyinstaller_install_hint()}")

    command = [pyinstaller, "--noconfirm", "--clean", "--name", config.app_name]

    if config.windowed:
        command.append("--windowed")
    if config.onefile:
        command.append("--onefile")

    for add_data in config.add_data:
        command.extend(["--add-data", add_data])

    for module in config.collect_submodules:
        command.extend(["--collect-submodules", module])

    for module in config.hidden_imports:
        command.extend(["--hidden-import", module])

    command.append(config.entrypoint)
    run(command, cwd=config.root)

    if not config.dist_binary.is_file():
        raise RuntimeError(f"PyInstaller did not create {config.dist_binary}")


def write_desktop_file(config: PackageConfig) -> None:
    if config.desktop is None:
        return

    desktop_file = config.desktop_file
    assert desktop_file is not None
    desktop_file.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={config.desktop.name}",
    ]

    if config.desktop.generic_name:
        lines.append(f"GenericName={config.desktop.generic_name}")
    if config.desktop.comment:
        lines.append(f"Comment={config.desktop.comment}")

    lines.extend(
        [
            f"Exec=/usr/bin/{config.app_name}",
            f"Icon={config.desktop.icon}",
            f"Terminal={'true' if config.desktop.terminal else 'false'}",
            f"Categories={config.desktop.categories}",
        ]
    )

    if config.desktop.startup_wm_class:
        lines.append(f"StartupWMClass={config.desktop.startup_wm_class}")

    lines.append("")
    desktop_file.write_text("\n".join(lines), encoding="utf-8")


def parse_mode(mode: str | None, default: int) -> int:
    if mode is None:
        return default
    return int(mode, 8)


def package_root_target(config: PackageConfig, target: str) -> Path:
    normalized = target.lstrip("/")
    if not normalized:
        return config.pkgroot
    return config.pkgroot / normalized


def install_static_file(source: Path, target: Path, mode: int) -> None:
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        target.chmod(0o755)
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target.chmod(mode)


def install_static_directory(source: Path, target: Path, file_mode: int) -> None:
    if not source.is_dir():
        raise RuntimeError(f"Install source is not a directory: {source}")

    target.mkdir(parents=True, exist_ok=True)

    for path in source.rglob("*"):
        relative_path = path.relative_to(source)
        target_path = target / relative_path

        if path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target_path)
            target_path.chmod(file_mode)


def install_static_entries(config: PackageConfig) -> None:
    for entry in config.install_entries:
        source = config.root / entry.source
        if not source.exists():
            raise RuntimeError(f"Install source does not exist: {source}")

        target = package_root_target(config, entry.target)
        mode = parse_mode(entry.mode, 0o644)

        if entry.recursive:
            install_static_directory(source, target, mode)
        else:
            install_static_file(source, target, mode)


def install_files_to_pkgroot(config: PackageConfig) -> int:
    if config.pkgroot.exists():
        shutil.rmtree(config.pkgroot)

    config.pkgroot.mkdir(parents=True, exist_ok=True)

    if has_binary(config):
        binary_target = config.pkgroot / "usr" / "bin" / config.app_name
        binary_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.dist_binary, binary_target)
        binary_target.chmod(0o755)

    if config.desktop is not None:
        desktop_file = config.desktop_file
        assert desktop_file is not None
        desktop_target = (
            config.pkgroot
            / "usr"
            / "share"
            / "applications"
            / f"{config.desktop.app_id}.desktop"
        )
        desktop_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(desktop_file, desktop_target)
        desktop_target.chmod(0o644)

    install_static_entries(config)

    total_size = 0
    for path in config.pkgroot.rglob("*"):
        if path.is_file():
            total_size += path.stat().st_size
    return total_size


def shell_array(values: list[str]) -> str:
    return " ".join(f"'{value}'" for value in values)


def render_pkgbuild(config: PackageConfig, version: str, pkgrel: str) -> Path:
    template_path = config.root / "PKGBUILD.in"
    if not template_path.is_file():
        raise RuntimeError(f"Missing PKGBUILD template: {template_path}")

    pkgbuild_dir = config.build_dir / "makepkg"
    if pkgbuild_dir.exists():
        shutil.rmtree(pkgbuild_dir)
    pkgbuild_dir.mkdir(parents=True)

    source_files = []

    if has_binary(config):
        shutil.copy2(config.dist_binary, pkgbuild_dir / config.app_name)
        source_files.append(config.app_name)
    if config.desktop is not None:
        desktop_file = config.desktop_file
        assert desktop_file is not None
        desktop_name = f"{config.desktop.app_id}.desktop"
        shutil.copy2(desktop_file, pkgbuild_dir / desktop_name)
        source_files.append(desktop_name)

    static_install_lines = []
    for index, entry in enumerate(config.install_entries):
        source = config.root / entry.source
        if not source.exists():
            raise RuntimeError(f"Install source does not exist: {source}")

        source_name = f"static-{index}-{source.name}"
        package_source = pkgbuild_dir / source_name
        if source.is_dir():
            shutil.copytree(source, package_source)
        else:
            shutil.copy2(source, package_source)
        source_files.append(source_name)

        target = entry.target.lstrip("/")
        mode = entry.mode or "0644"
        if entry.recursive:
            static_install_lines.append(
                f"    install -dm755 \"$pkgdir/{target}\"\n"
                f"    cp -a \"$srcdir/{source_name}/.\" \"$pkgdir/{target}/\"\n"
                f"    find \"$pkgdir/{target}\" -type f -exec chmod {mode} {{}} +"
            )
        elif source.is_dir():
            static_install_lines.append(f"    install -dm755 \"$pkgdir/{target}\"")
        else:
            static_install_lines.append(
                f"    install -Dm{mode} \"$srcdir/{source_name}\" \"$pkgdir/{target}\""
            )

    substitutions = {
        "pkgname": config.name,
        "pkgver": version,
        "pkgrel": pkgrel,
        "pkgdesc": config.description,
        "arch": shell_array([config.arch]),
        "url": config.url,
        "license": shell_array([config.license]),
        "depends": shell_array(config.dependencies),
        "source": shell_array(source_files),
        "sha256sums": shell_array(["SKIP"] * len(source_files)),
        "app_name": config.app_name,
        "desktop_app_id": config.desktop.app_id if config.desktop else "",
        "static_install": "\n".join(static_install_lines),
    }

    template = Template(template_path.read_text(encoding="utf-8"))
    (pkgbuild_dir / "PKGBUILD").write_text(template.safe_substitute(substitutions), encoding="utf-8")
    return pkgbuild_dir


def build_with_makepkg(config: PackageConfig, version: str, pkgrel: str) -> Path:
    pkgbuild_dir = render_pkgbuild(config, version, pkgrel)
    run(["makepkg", "--force", "--clean", "--cleanbuild"], cwd=pkgbuild_dir)

    package_files = sorted(pkgbuild_dir.glob(f"{config.name}-{version}-{pkgrel}-*.pkg.tar.*"))
    if not package_files:
        raise RuntimeError("makepkg finished but no package file was produced")

    config.package_out_dir.mkdir(parents=True, exist_ok=True)
    output = config.package_out_dir / package_files[-1].name
    shutil.copy2(package_files[-1], output)
    return output


def add_tar_entry(archive: tarfile.TarFile, source: Path, archive_name: str, mode: int) -> None:
    info = archive.gettarinfo(str(source), arcname=archive_name)
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mode = mode

    if source.is_dir():
        archive.addfile(info)
    else:
        with source.open("rb") as source_file:
            archive.addfile(info, source_file)


def write_direct_pkginfo(
    config: PackageConfig,
    version: str,
    pkgrel: str,
    installed_size: int,
    packager: str,
) -> None:
    lines = [
        f"pkgname = {config.name}",
        f"pkgbase = {config.name}",
        "xdata = pkgtype=pkg",
        f"pkgver = {version}-{pkgrel}",
        f"pkgdesc = {config.description}",
        f"url = {config.url}",
        f"builddate = {int(time.time())}",
        f"packager = {packager}",
        f"size = {installed_size}",
        f"arch = {config.arch}",
        f"license = {config.license}",
    ]
    lines.extend(f"depend = {dependency}" for dependency in config.dependencies)
    lines.append("")
    (config.pkgroot / ".PKGINFO").write_text("\n".join(lines), encoding="utf-8")


def build_direct_package(config: PackageConfig, version: str, pkgrel: str, packager: str) -> Path:
    installed_size = install_files_to_pkgroot(config)
    write_direct_pkginfo(config, version, pkgrel, installed_size, packager)

    config.package_out_dir.mkdir(parents=True, exist_ok=True)
    uncompressed = config.build_dir / f"{config.name}-{version}-{pkgrel}-{config.arch}.pkg.tar"
    output = config.package_out_dir / f"{config.name}-{version}-{pkgrel}-{config.arch}.pkg.tar.zst"

    with tarfile.open(uncompressed, "w", format=tarfile.PAX_FORMAT) as archive:
        add_tar_entry(archive, config.pkgroot / ".PKGINFO", ".PKGINFO", 0o644)
        for path in sorted(config.pkgroot.rglob("*")):
            if path.name == ".PKGINFO":
                continue
            archive_name = path.relative_to(config.pkgroot).as_posix()
            if path.is_dir():
                add_tar_entry(archive, path, archive_name, 0o755)
            elif path.is_file():
                mode = 0o755 if os.access(path, os.X_OK) else 0o644
                add_tar_entry(archive, path, archive_name, mode)

    zstd = shutil.which("zstd")
    if zstd is None:
        raise RuntimeError("makepkg was not found and direct packaging requires zstd")

    if output.exists():
        output.unlink()

    run([zstd, "--force", "--rm", "-19", str(uncompressed), "-o", str(output)], cwd=config.root)
    return output


def resolve_package(package_arg: str) -> Path:
    package_path = Path(package_arg)
    if package_path.is_dir():
        return package_path.resolve()

    package_path = PACKAGES_DIR / package_arg
    if package_path.is_dir():
        return package_path.resolve()

    raise RuntimeError(f"Package not found: {package_arg}")


def build_package(args: argparse.Namespace) -> Path:
    config = read_config(resolve_package(args.package))

    if args.clean:
        clean(config)

    config.build_dir.mkdir(parents=True, exist_ok=True)
    config.package_out_dir.mkdir(parents=True, exist_ok=True)

    if has_binary(config):
        build_binary(config)
        write_desktop_file(config)

    makepkg = shutil.which("makepkg")
    if makepkg and is_arch_like_host() and not args.direct:
        print("Arch-like host detected; building package with makepkg")
        return build_with_makepkg(config, args.version, args.pkgrel)

    if makepkg and not is_arch_like_host():
        print("makepkg found, but host is not Arch-like; using direct packaging")
    elif args.direct:
        print("--direct used; building package directly")
    else:
        print("makepkg not found; building package directly")

    return build_direct_package(config, args.version, args.pkgrel, args.packager)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Amethyne Python app packages.")
    parser.add_argument("package", help="Package name under packages/ or path to package directory.")
    parser.add_argument("--version", default="0.1.0", help="Package version. Default: 0.1.0")
    parser.add_argument("--pkgrel", default="1", help="Package release number. Default: 1")
    parser.add_argument(
        "--packager",
        default=os.environ.get("PACKAGER", DEFAULT_PACKAGER),
        help=f"Packager string for direct package metadata. Default: {DEFAULT_PACKAGER}",
    )
    parser.add_argument("--clean", action="store_true", help="Remove package build output first.")
    parser.add_argument("--direct", action="store_true", help="Skip makepkg and write .pkg.tar.zst directly.")
    return parser.parse_args()


def main() -> int:
    try:
        package = build_package(parse_args())
    except RuntimeError as error:
        print(f"error: {error}", file=os.sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(
            f"error: command failed with exit code {error.returncode}: {' '.join(error.cmd)}",
            file=os.sys.stderr,
        )
        return error.returncode

    print(f"Built package: {package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
