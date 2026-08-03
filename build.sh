#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PRESET_PREFIX="amethyne"
IMAGE_NAME="amethyne-linux-builder"
PROJECT_DIR="$(pwd)"
FORCE_REBUILD_PACKAGES=false
REPO_MODE=false
REPO_HOST="0.0.0.0"
REPO_PORT="8080"
PACKAGE_VERSION=""
PACKAGE_REL="1"
PACKAGE_REL_EXPLICIT=false

usage() {
    cat <<EOF
Usage: ./build.sh [options] [preset]

Options:
  --repo                   Build/collect local packages into a pacman repo and serve it over HTTP instead of building an ISO.
  --repo-host VALUE        Host/interface for --repo HTTP server. Default: ${REPO_HOST}
  --repo-port VALUE        Port for --repo HTTP server. Default: ${REPO_PORT}
  --rebuild-packages       Force rebuilding local Amethyne packages before ISO build or repo serving.
  --package-version VALUE  Override version for all local Amethyne packages. Defaults to each package's package.toml version.
  --package-rel VALUE      Package release to use for local Amethyne packages. Default: ${PACKAGE_REL}
                           In --repo mode, omitted pkgrel reuses/bump state from .build/<preset>/version-state.
  -h, --help               Show this help message.

Examples:
  ./build.sh
  ./build.sh amethyne
  ./build.sh --rebuild-packages
  ./build.sh --repo
  ./build.sh --repo --rebuild-packages        # auto-bumps pkgrel, e.g. 0.1.0-2
  ./build.sh --repo --repo-port 8081
  ./build.sh --package-version 0.2.0 --rebuild-packages amethyne
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)
            REPO_MODE=true
            ;;
        --repo-host)
            if [[ $# -lt 2 ]]; then
                echo "error: --repo-host requires a value" >&2
                exit 1
            fi
            REPO_HOST="$2"
            shift
            ;;
        --repo-port)
            if [[ $# -lt 2 ]]; then
                echo "error: --repo-port requires a value" >&2
                exit 1
            fi
            REPO_PORT="$2"
            shift
            ;;
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
            PACKAGE_REL_EXPLICIT=true
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

VERSION_STATE_FILE=".build/${PRESET_PREFIX}/version-state"

if [[ "${REPO_MODE}" == true && "${PACKAGE_REL_EXPLICIT}" == false ]]; then
    STATE_PACKAGE_VERSION=""
    STATE_PACKAGE_REL=""
    if [[ -f "${VERSION_STATE_FILE}" ]]; then
        # shellcheck disable=SC1090
        source "${VERSION_STATE_FILE}"
    fi

    if [[ "${FORCE_REBUILD_PACKAGES}" == true ]]; then
        if [[ "${STATE_PACKAGE_REL}" =~ ^[0-9]+$ ]]; then
            PACKAGE_REL="$((10#${STATE_PACKAGE_REL} + 1))"
        else
            PACKAGE_REL="2"
        fi
        echo "==> Auto package release for dev repo: pkgrel ${PACKAGE_REL}"
    elif [[ "${STATE_PACKAGE_REL}" =~ ^[0-9]+$ ]]; then
        PACKAGE_REL="${STATE_PACKAGE_REL}"
        echo "==> Using remembered dev repo package release: pkgrel ${PACKAGE_REL}"
    else
        PACKAGE_REL="1"
    fi
fi

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

if [[ "${REPO_MODE}" == true ]]; then
    echo "==> Building package repository with preset: ${PRESET_PREFIX}"
else
    echo "==> Building ISO with preset: ${PRESET_PREFIX}"
fi

docker run --rm \
    --privileged \
    -e "PRESET_PREFIX=${PRESET_PREFIX}" \
    -e "FORCE_REBUILD_PACKAGES=${FORCE_REBUILD_PACKAGES}" \
    -e "BUILD_REPO_ONLY=${REPO_MODE}" \
    -e "PACKAGE_VERSION=${PACKAGE_VERSION}" \
    -e "PACKAGE_REL=${PACKAGE_REL}" \
    -e "HOST_UID=$(id -u)" \
    -e "HOST_GID=$(id -g)" \
    -v "${PROJECT_DIR}:/work" \
    "${IMAGE_NAME}" \
    /work/scripts/container-build.sh

if [[ "${REPO_MODE}" == true ]]; then
    mkdir -p "$(dirname "${VERSION_STATE_FILE}")"
    cat > "${VERSION_STATE_FILE}" <<EOF
STATE_PACKAGE_REL="${PACKAGE_REL}"
EOF

    REPO_DIR="${PROJECT_DIR}/.build/${PRESET_PREFIX}/package-repo"
    if [[ ! -f "${REPO_DIR}/amethyne-dev.db.tar.gz" ]]; then
        echo "error: expected repo database not found: ${REPO_DIR}/amethyne-dev.db.tar.gz" >&2
        exit 1
    fi

    cat <<EOF
==> Serving package repository: ${REPO_DIR}
==> Pacman config for NAT/QEMU guests:

[amethyne-dev]
SigLevel = Optional TrustAll
Server = http://192.168.122.1:${REPO_PORT}

==> Starting HTTP server on ${REPO_HOST}:${REPO_PORT}
==> Press Ctrl+C to stop serving the repository.
EOF
    python3 -m http.server "${REPO_PORT}" --bind "${REPO_HOST}" --directory "${REPO_DIR}"
    exit 0
fi
