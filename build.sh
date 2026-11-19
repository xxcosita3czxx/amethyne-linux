#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PRESET_PREFIX="amethyne"
IMAGE_NAME="amethyne-linux-builder"
PROJECT_DIR="$(pwd)"
FORCE_REBUILD_PACKAGES=false
REPO_MODE=false
REPO_WATCH=false
REPO_WATCH_INTERVAL="1"
REPO_HOST="0.0.0.0"
REPO_PORT="8080"
PACKAGE_FILTERS=()
PACKAGE_VERSION=""
PACKAGE_REL="1"
PACKAGE_REL_EXPLICIT=false

usage() {
    cat <<EOF
Usage: ./build.sh [options] [preset]

Options:
  --repo                   Build/collect local packages into a pacman repo and serve it over HTTP instead of building an ISO.
  --watch                  With --repo, watch package sources and refresh the served repo when files change.
  --watch-interval VALUE   Poll interval in seconds for --watch. Default: ${REPO_WATCH_INTERVAL}
  --repo-host VALUE        Host/interface for --repo HTTP server. Default: ${REPO_HOST}
  --repo-port VALUE        Port for --repo HTTP server. Default: ${REPO_PORT}
  -p, --package NAME       Only build/collect one package. Can be used multiple times.
  --rebuild-packages       Force rebuilding selected/local Amethyne packages before ISO build or repo serving.
  --package-version VALUE  Override version for all local Amethyne packages. Defaults to each package's package.toml version.
  --package-rel VALUE      Package release to use for local Amethyne packages. Default: ${PACKAGE_REL}
                           In --repo mode, omitted pkgrel reuses/bump state from .build/<preset>/version-state.
  -h, --help               Show this help message.

Examples:
  ./build.sh
  ./build.sh amethyne
  ./build.sh --rebuild-packages
  ./build.sh --repo
  ./build.sh --repo --watch --package amethyne-desktop
  ./build.sh --repo --rebuild-packages        # auto-bumps pkgrel, e.g. 0.1.0-2
  ./build.sh --repo --rebuild-packages --package amethyne-desktop
  ./build.sh --repo --repo-port 8081
  ./build.sh --package-version 0.2.0 --rebuild-packages amethyne
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)
            REPO_MODE=true
            ;;
        --watch)
            REPO_WATCH=true
            REPO_MODE=true
            ;;
        --watch-interval)
            if [[ $# -lt 2 ]]; then
                echo "error: --watch-interval requires a value" >&2
                exit 1
            fi
            REPO_WATCH_INTERVAL="$2"
            shift
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
        -p|--package)
            if [[ $# -lt 2 ]]; then
                echo "error: $1 requires a value" >&2
                exit 1
            fi
            PACKAGE_FILTERS+=("$2")
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
PACKAGE_FILTERS_VALUE=""
if [[ ${#PACKAGE_FILTERS[@]} -gt 0 ]]; then
    PACKAGE_FILTERS_VALUE="${PACKAGE_FILTERS[*]}"
    echo "==> Package filter: ${PACKAGE_FILTERS_VALUE}"
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "error: docker is required to build Amethyne Linux" >&2
    exit 1
fi

if [[ ! -f "./presets/${PRESET_PREFIX}.preset.sh" ]]; then
    echo "error: preset not found: ./presets/${PRESET_PREFIX}.preset.sh" >&2
    exit 1
fi

load_package_rel_state() {
    STATE_PACKAGE_REL=""
    if [[ -f "${VERSION_STATE_FILE}" ]]; then
        # shellcheck disable=SC1090
        source "${VERSION_STATE_FILE}"
    fi
}

resolve_initial_package_rel() {
    if [[ "${REPO_MODE}" != true || "${PACKAGE_REL_EXPLICIT}" == true ]]; then
        return
    fi

    load_package_rel_state
    if [[ "${FORCE_REBUILD_PACKAGES}" == true ]]; then
        bump_package_rel
        echo "==> Auto package release for dev repo: pkgrel ${PACKAGE_REL}"
    elif [[ "${STATE_PACKAGE_REL}" =~ ^[0-9]+$ ]]; then
        PACKAGE_REL="${STATE_PACKAGE_REL}"
        echo "==> Using remembered dev repo package release: pkgrel ${PACKAGE_REL}"
    else
        PACKAGE_REL="1"
    fi
}

bump_package_rel() {
    if [[ "${PACKAGE_REL_EXPLICIT}" == true ]]; then
        return
    fi

    load_package_rel_state
    if [[ "${STATE_PACKAGE_REL}" =~ ^[0-9]+$ ]]; then
        PACKAGE_REL="$((10#${STATE_PACKAGE_REL} + 1))"
    elif [[ "${PACKAGE_REL}" =~ ^[0-9]+$ ]]; then
        PACKAGE_REL="$((10#${PACKAGE_REL} + 1))"
    else
        PACKAGE_REL="2"
    fi
}

save_package_rel_state() {
    mkdir -p "$(dirname "${VERSION_STATE_FILE}")"
    cat > "${VERSION_STATE_FILE}" <<EOF
STATE_PACKAGE_REL="${PACKAGE_REL}"
EOF
}

run_container_build() {
    local force_rebuild="$1"
    local repo_only="$2"

    docker run --rm \
        --privileged \
        -e "PRESET_PREFIX=${PRESET_PREFIX}" \
        -e "FORCE_REBUILD_PACKAGES=${force_rebuild}" \
        -e "BUILD_REPO_ONLY=${repo_only}" \
        -e "PACKAGE_FILTERS=${PACKAGE_FILTERS_VALUE}" \
        -e "PACKAGE_VERSION=${PACKAGE_VERSION}" \
        -e "PACKAGE_REL=${PACKAGE_REL}" \
        -e "HOST_UID=$(id -u)" \
        -e "HOST_GID=$(id -g)" \
        -v "${PROJECT_DIR}:/work" \
        "${IMAGE_NAME}" \
        /work/scripts/container-build.sh
}

selected_package_dirs() {
    local package_dir
    local package_name
    local filter
    local selected

    for package_dir in ./packages/*; do
        [[ -d "${package_dir}" && -f "${package_dir}/package.toml" ]] || continue
        if [[ ${#PACKAGE_FILTERS[@]} -eq 0 ]]; then
            printf '%s\n' "${package_dir}"
            continue
        fi

        package_name=$(python3 - "${package_dir}/package.toml" <<'PY'
import sys, tomllib
with open(sys.argv[1], 'rb') as f:
    print(tomllib.load(f)['package'].get('name', ''))
PY
)
        selected=false
        for filter in "${PACKAGE_FILTERS[@]}"; do
            if [[ "${filter}" == "$(basename "${package_dir}")" || "${filter}" == "${package_name}" ]]; then
                selected=true
                break
            fi
        done
        if [[ "${selected}" == true ]]; then
            printf '%s\n' "${package_dir}"
        fi
    done
}

package_source_stamp() {
    selected_package_dirs | while IFS= read -r package_dir; do
        find "${package_dir}" \
            -path "${package_dir}/build" -prune -o \
            -path "${package_dir}/dist" -prune -o \
            -path "${package_dir}/packages" -prune -o \
            -type f \
            -printf '%T@ %p\n'
    done | sort
}

start_repo_server() {
    local repo_dir="$1"
    cat <<EOF
==> Serving package repository: ${repo_dir}
==> Pacman config for NAT/QEMU guests:

[amethyne-dev]
SigLevel = Optional TrustAll
Server = http://192.168.122.1:${REPO_PORT}

==> Starting HTTP server on ${REPO_HOST}:${REPO_PORT}
==> Press Ctrl+C to stop serving the repository.
EOF
    python3 -m http.server "${REPO_PORT}" --bind "${REPO_HOST}" --directory "${repo_dir}"
}

start_repo_server_background() {
    local repo_dir="$1"
    start_repo_server "${repo_dir}" &
    SERVER_PID="$!"
    trap 'kill "${SERVER_PID}" 2>/dev/null || true; wait "${SERVER_PID}" 2>/dev/null || true; exit 0' INT TERM EXIT
}

resolve_initial_package_rel

echo "==> Building Docker image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" .

if [[ "${REPO_MODE}" == true ]]; then
    echo "==> Building package repository with preset: ${PRESET_PREFIX}"
else
    echo "==> Building ISO with preset: ${PRESET_PREFIX}"
fi

run_container_build "${FORCE_REBUILD_PACKAGES}" "${REPO_MODE}"

if [[ "${REPO_MODE}" == true ]]; then
    save_package_rel_state

    REPO_DIR="${PROJECT_DIR}/.build/${PRESET_PREFIX}/package-repo"
    if [[ ! -f "${REPO_DIR}/amethyne-dev.db.tar.gz" ]]; then
        echo "error: expected repo database not found: ${REPO_DIR}/amethyne-dev.db.tar.gz" >&2
        exit 1
    fi

    if [[ "${REPO_WATCH}" == true ]]; then
        LAST_STAMP="$(package_source_stamp)"
        start_repo_server_background "${REPO_DIR}"
        echo "==> Watching package sources every ${REPO_WATCH_INTERVAL}s"
        while true; do
            sleep "${REPO_WATCH_INTERVAL}"
            CURRENT_STAMP="$(package_source_stamp)"
            if [[ "${CURRENT_STAMP}" != "${LAST_STAMP}" ]]; then
                echo "==> Package source change detected; refreshing dev repo"
                bump_package_rel
                echo "==> Auto package release for dev repo: pkgrel ${PACKAGE_REL}"
                if run_container_build true true; then
                    save_package_rel_state
                    LAST_STAMP="$(package_source_stamp)"
                    echo "==> Dev repo refreshed"
                else
                    echo "error: dev repo refresh failed; keeping server running" >&2
                fi
            fi
        done
    fi

    start_repo_server "${REPO_DIR}"
    exit 0
fi
