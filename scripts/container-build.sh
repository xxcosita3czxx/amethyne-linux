#!/usr/bin/env bash
set -euo pipefail

cd /work

PRESET_PREFIX="${PRESET_PREFIX:-amethyne}"
FORCE_REBUILD_PACKAGES="${FORCE_REBUILD_PACKAGES:-false}"
PACKAGE_VERSION="${PACKAGE_VERSION:-0.1.0}"
PACKAGE_REL="${PACKAGE_REL:-1}"
PRESET_FILE="./presets/${PRESET_PREFIX}.preset.sh"
ARCHISO_PROFILE_DIR="./presets/${PRESET_PREFIX}.archiso"
AIROOTFS_DIR="./presets/${PRESET_PREFIX}.airootfs"
BUILD_ROOT="./.build/${PRESET_PREFIX}"
PROFILE_DIR="${BUILD_ROOT}/profile"
WORK_DIR="./work/${PRESET_PREFIX}"
OUT_DIR="./out/${PRESET_PREFIX}"
PACKAGE_REPO_NAME="amethyne-local"
PACKAGE_REPO_DIR="${BUILD_ROOT}/package-repo"
HAVE_LOCAL_REPO=false

read_package_field() {
    local package_config="$1"
    local field="$2"

    python3 - "$package_config" "$field" <<'PY'
import sys
import tomllib
from pathlib import Path

config = Path(sys.argv[1])
field = sys.argv[2]
with config.open("rb") as config_file:
    data = tomllib.load(config_file)
package = data["package"]
print(package.get(field, ""))
PY
}

build_local_packages() {
    local package_configs=()
    local package_config
    local package_dir
    local package_basename
    local package_name
    local package_arch
    local package_glob
    local package_file

    while IFS= read -r -d '' package_config; do
        package_configs+=("$package_config")
    done < <(find ./packages -mindepth 2 -maxdepth 2 -name package.toml -print0 | sort -z)

    if [[ ${#package_configs[@]} -eq 0 ]]; then
        echo "==> No local Amethyne packages found"
        HAVE_LOCAL_REPO=false
        return 0
    fi

    echo "==> Preparing local package repository: ${PACKAGE_REPO_DIR}"
    rm -rf "${PACKAGE_REPO_DIR}"
    mkdir -p "${PACKAGE_REPO_DIR}"

    for package_config in "${package_configs[@]}"; do
        package_dir="$(dirname "$package_config")"
        package_basename="$(basename "$package_dir")"
        package_name="$(read_package_field "$package_config" name)"
        package_arch="$(read_package_field "$package_config" arch)"

        if [[ -z "$package_name" ]]; then
            echo "error: package name missing in ${package_config}" >&2
            exit 1
        fi

        if [[ -z "$package_arch" ]]; then
            package_arch="x86_64"
        fi

        package_glob="${package_dir}/packages/${package_name}-${PACKAGE_VERSION}-${PACKAGE_REL}-${package_arch}.pkg.tar.*"

        should_build=false
        if [[ "${FORCE_REBUILD_PACKAGES}" == true ]]; then
            should_build=true
            build_reason="forced"
        elif ! compgen -G "${package_glob}" >/dev/null; then
            should_build=true
            build_reason="missing"
        else
            package_file="$(find "${package_dir}/packages" -maxdepth 1 -type f -name "${package_name}-${PACKAGE_VERSION}-${PACKAGE_REL}-${package_arch}.pkg.tar.*" | sort | tail -n 1)"
            if find "${package_dir}" \
                -path "${package_dir}/build" -prune -o \
                -path "${package_dir}/dist" -prune -o \
                -path "${package_dir}/packages" -prune -o \
                -type f \
                -newer "${package_file}" \
                -print -quit | grep -q .; then
                should_build=true
                build_reason="stale"
            fi
        fi

        if [[ "${should_build}" == true ]]; then
            echo "==> Building local package (${build_reason}): ${package_name}"
            ./package-builder.py \
                "${package_basename}" \
                --version "${PACKAGE_VERSION}" \
                --pkgrel "${PACKAGE_REL}" \
                --direct \
                --clean
        else
            echo "==> Reusing existing local package: ${package_name}"
        fi

        if ! compgen -G "${package_glob}" >/dev/null; then
            echo "error: expected package was not produced: ${package_glob}" >&2
            exit 1
        fi

        package_file="$(find "${package_dir}/packages" -maxdepth 1 -type f -name "${package_name}-${PACKAGE_VERSION}-${PACKAGE_REL}-${package_arch}.pkg.tar.*" | sort | tail -n 1)"
        cp -f "${package_file}" "${PACKAGE_REPO_DIR}/"
    done

    echo "==> Creating pacman repo database: ${PACKAGE_REPO_NAME}"
    repo-add "${PACKAGE_REPO_DIR}/${PACKAGE_REPO_NAME}.db.tar.gz" "${PACKAGE_REPO_DIR}"/*.pkg.tar.*
    HAVE_LOCAL_REPO=true
}

if [[ ! -f "${PRESET_FILE}" ]]; then
    echo "error: preset not found: ${PRESET_FILE}" >&2
    exit 1
fi

# shellcheck disable=SC1090
source "${PRESET_FILE}"

: "${ISO_NAME:?ISO_NAME is required in ${PRESET_FILE}}"
: "${ISO_LABEL:?ISO_LABEL is required in ${PRESET_FILE}}"
: "${ISO_PUBLISHER:?ISO_PUBLISHER is required in ${PRESET_FILE}}"
: "${ISO_APPLICATION:?ISO_APPLICATION is required in ${PRESET_FILE}}"
: "${INSTALL_DIR:?INSTALL_DIR is required in ${PRESET_FILE}}"
: "${ARCH:?ARCH is required in ${PRESET_FILE}}"
: "${KERNEL_IMAGE:?KERNEL_IMAGE is required in ${PRESET_FILE}}"
: "${INITRAMFS_IMAGE:?INITRAMFS_IMAGE is required in ${PRESET_FILE}}"
: "${PACMAN_CONF:?PACMAN_CONF is required in ${PRESET_FILE}}"

if ! declare -p BASE_PACKAGES >/dev/null 2>&1; then
    echo "error: BASE_PACKAGES array is required in ${PRESET_FILE}" >&2
    exit 1
fi

if ! declare -p LIVE_PACKAGES >/dev/null 2>&1; then
    echo "error: LIVE_PACKAGES array is required in ${PRESET_FILE}" >&2
    exit 1
fi

if ! declare -p INSTALL_PACKAGES >/dev/null 2>&1; then
    INSTALL_PACKAGES=()
fi

build_local_packages

echo "==> Preparing archiso profile: ${PROFILE_DIR}"
rm -rf "${PROFILE_DIR}"
mkdir -p "${PROFILE_DIR}" "${WORK_DIR}" "${OUT_DIR}"

if [[ ! -d "${ARCHISO_PROFILE_DIR}" ]]; then
    echo "error: archiso profile skeleton not found: ${ARCHISO_PROFILE_DIR}" >&2
    exit 1
fi

cp -a "${ARCHISO_PROFILE_DIR}/." "${PROFILE_DIR}/"

ISO_VERSION_VALUE="${ISO_VERSION:-$(date +%Y.%m.%d)}"
find "${PROFILE_DIR}" -type f \( -name '*.sh' -o -name '*.cfg' \) -print0 | while IFS= read -r -d '' config_file; do
    sed -i \
        -e "s|%ISO_NAME%|${ISO_NAME}|g" \
        -e "s|%ISO_LABEL%|${ISO_LABEL}|g" \
        -e "s|%ISO_PUBLISHER%|${ISO_PUBLISHER}|g" \
        -e "s|%ISO_APPLICATION%|${ISO_APPLICATION}|g" \
        -e "s|%ISO_VERSION%|${ISO_VERSION_VALUE}|g" \
        -e "s|%INSTALL_DIR%|${INSTALL_DIR}|g" \
        -e "s|%ARCH%|${ARCH}|g" \
        -e "s|%KERNEL_IMAGE%|${KERNEL_IMAGE}|g" \
        -e "s|%INITRAMFS_IMAGE%|${INITRAMFS_IMAGE}|g" \
        "${config_file}"
done

printf '%s\n' "${PACMAN_CONF}" > "${PROFILE_DIR}/pacman.conf"

if [[ "${HAVE_LOCAL_REPO}" == true ]]; then
    cat >> "${PROFILE_DIR}/pacman.conf" <<EOF

[${PACKAGE_REPO_NAME}]
SigLevel = Optional TrustAll
Server = file:///work/${PACKAGE_REPO_DIR#./}
EOF
fi

# The preset is the source of truth for installed packages. Local Amethyne
# packages are made available through the generated pacman repo above, but they
# must still be listed in BASE_PACKAGES or LIVE_PACKAGES to be installed.
printf '%s\n' "${BASE_PACKAGES[@]}" "${LIVE_PACKAGES[@]}" > "${PROFILE_DIR}/packages.${ARCH}"

mkdir -p "${PROFILE_DIR}/airootfs"
if [[ -d "${AIROOTFS_DIR}" ]]; then
    cp -a "${AIROOTFS_DIR}/." "${PROFILE_DIR}/airootfs/"
fi


INSTALLER_DATA_DIR="${PROFILE_DIR}/airootfs/usr/share/amethyne/installer"
mkdir -p "${INSTALLER_DATA_DIR}/packages"

# Runtime metadata for the future installer. These are the raw preset package
# groups; installer code can combine them as needed.
printf '%s\n' "${BASE_PACKAGES[@]}" > "${INSTALLER_DATA_DIR}/packages/base.${ARCH}"
printf '%s\n' "${LIVE_PACKAGES[@]}" > "${INSTALLER_DATA_DIR}/packages/live.${ARCH}"
printf '%s\n' "${INSTALL_PACKAGES[@]:-}" > "${INSTALLER_DATA_DIR}/packages/install.${ARCH}"

cp -f "${PROFILE_DIR}/pacman.conf" "${INSTALLER_DATA_DIR}/pacman.conf"
if [[ "${HAVE_LOCAL_REPO}" == true ]]; then
    mkdir -p "${INSTALLER_DATA_DIR}/repo"

    copied_installer_package=false
    for package_name in "${BASE_PACKAGES[@]}" "${INSTALL_PACKAGES[@]:-}"; do
        for package_file in "${PACKAGE_REPO_DIR}/${package_name}-${PACKAGE_VERSION}-${PACKAGE_REL}-"*.pkg.tar.*; do
            [[ -e "${package_file}" ]] || continue
            cp -f "${package_file}" "${INSTALLER_DATA_DIR}/repo/"
            copied_installer_package=true
        done
    done

    if [[ "${copied_installer_package}" == true ]]; then
        repo-add "${INSTALLER_DATA_DIR}/repo/${PACKAGE_REPO_NAME}.db.tar.gz" "${INSTALLER_DATA_DIR}/repo"/*.pkg.tar.*
        sed -i \
            "s|file:///work/${PACKAGE_REPO_DIR#./}|file:///usr/share/amethyne/installer/repo|g" \
            "${INSTALLER_DATA_DIR}/pacman.conf"
    fi
fi

if [[ -d "${AIROOTFS_DIR}" ]]; then
    mkdir -p "${INSTALLER_DATA_DIR}/airootfs"
    cp -a "${AIROOTFS_DIR}/." "${INSTALLER_DATA_DIR}/airootfs/"
    rm -f "${INSTALLER_DATA_DIR}/airootfs/root/customize_airootfs.sh"
    rmdir --ignore-fail-on-non-empty "${INSTALLER_DATA_DIR}/airootfs/root" 2>/dev/null || true
fi

echo "==> Package count: $(wc -l < "${PROFILE_DIR}/packages.${ARCH}")"
echo "==> Running mkarchiso"
mkarchiso -v -w "${WORK_DIR}" -o "${OUT_DIR}" "${PROFILE_DIR}"

if [[ -n "${HOST_UID:-}" && -n "${HOST_GID:-}" ]]; then
    chown -R "${HOST_UID}:${HOST_GID}" ./.build ./work ./out ./packages/*/build ./packages/*/dist ./packages/*/packages || true
fi

echo "==> Done. ISO output: ${OUT_DIR}"
