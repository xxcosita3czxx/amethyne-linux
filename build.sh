#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PRESET_PREFIX="amethyne"
IMAGE_NAME="amethyne-linux-builder"
PROJECT_DIR="$(pwd)"
FORCE_REBUILD_PACKAGES=false
PACKAGE_VERSION="0.1.0"
PACKAGE_REL="1"

usage() {
    cat <<EOF
Usage: ./build.sh [options] [preset]

Options:
  --rebuild-packages       Force rebuilding local Amethyne packages before ISO build.
  --package-version VALUE  Version to use for local Amethyne packages. Default: ${PACKAGE_VERSION}
  --package-rel VALUE      Package release to use for local Amethyne packages. Default: ${PACKAGE_REL}
  -h, --help               Show this help message.

Examples:
  ./build.sh
  ./build.sh amethyne
  ./build.sh --rebuild-packages
  ./build.sh --package-version 0.2.0 --rebuild-packages amethyne
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rebuild-packages)
            FORCE_REBUILD_PACKAGES=true
            ;;
        --package-version)
            if [[ $# -lt 2 ]]; then
                echo "error: --package-version requires a value" >&2
                exit 1
            fi
            PACKAGE_VERSION="$2"
            shift
            ;;
        --package-rel|--pkgrel)
            if [[ $# -lt 2 ]]; then
                echo "error: $1 requires a value" >&2
                exit 1
            fi
            PACKAGE_REL="$2"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --*)
            echo "error: unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
        *)
            PRESET_PREFIX="$1"
            ;;
    esac
    shift
done

if ! command -v docker >/dev/null 2>&1; then
    echo "error: docker is required to build Amethyne Linux" >&2
    exit 1
fi

if [[ ! -f "./presets/${PRESET_PREFIX}.preset.sh" ]]; then
    echo "error: preset not found: ./presets/${PRESET_PREFIX}.preset.sh" >&2
    exit 1
fi

echo "==> Building Docker image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" .

echo "==> Building ISO with preset: ${PRESET_PREFIX}"
docker run --rm \
    --privileged \
    -e "PRESET_PREFIX=${PRESET_PREFIX}" \
    -e "FORCE_REBUILD_PACKAGES=${FORCE_REBUILD_PACKAGES}" \
    -e "PACKAGE_VERSION=${PACKAGE_VERSION}" \
    -e "PACKAGE_REL=${PACKAGE_REL}" \
    -e "HOST_UID=$(id -u)" \
    -e "HOST_GID=$(id -g)" \
    -v "${PROJECT_DIR}:/work" \
    "${IMAGE_NAME}" \
    /work/scripts/container-build.sh
