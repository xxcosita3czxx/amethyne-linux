#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

IMAGE_NAME="amethyne-linux-builder"
CLEAN_DOCKER_IMAGE=false
CLEAN_DOCKER_CACHE=false
CLEAN_PACKAGES=false

usage() {
    cat <<EOF
Usage: ./clean.sh [options]

Options:
  --packages      Remove per-package build outputs under packages/*/{build,dist,packages} and *.spec.
  --docker        Remove the ${IMAGE_NAME} Docker image.
  --docker-cache  Prune Docker build cache. This affects global Docker build cache.
  --all           Clean project artifacts, package outputs, Docker image, and Docker build cache.
  -h, --help      Show this help message.

By default, this only removes project build outputs:
  .build/
  work/
  out/

Use --packages to also remove:
  packages/*/build/
  packages/*/dist/
  packages/*/packages/
  packages/*/*.spec
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --packages)
            CLEAN_PACKAGES=true
            ;;
        --docker)
            CLEAN_DOCKER_IMAGE=true
            ;;
        --docker-cache)
            CLEAN_DOCKER_CACHE=true
            ;;
        --all)
            CLEAN_PACKAGES=true
            CLEAN_DOCKER_IMAGE=true
            CLEAN_DOCKER_CACHE=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

echo "==> Removing project build artifacts"
if ! rm -rf ./.build ./work ./out 2>/dev/null; then
    if command -v docker >/dev/null 2>&1; then
        echo "==> Retrying artifact cleanup through Docker root"
        docker run --rm \
            -v "$(pwd):/work" \
            "${IMAGE_NAME}" \
            sh -c 'chmod -R u+rwX /work/.build /work/work /work/out 2>/dev/null || true; rm -rf /work/.build /work/work /work/out'
    else
        echo "error: failed to remove build artifacts and Docker is not available for root cleanup" >&2
        exit 1
    fi
fi

if [[ "${CLEAN_PACKAGES}" == true ]]; then
    echo "==> Removing package build artifacts"
    if ! find ./packages -mindepth 2 -maxdepth 2 \( -name build -o -name dist -o -name packages \) -exec rm -rf {} + 2>/dev/null || \
       ! find ./packages -mindepth 2 -maxdepth 2 -name '*.spec' -exec rm -f {} + 2>/dev/null; then
        if command -v docker >/dev/null 2>&1; then
            echo "==> Retrying package artifact cleanup through Docker root"
            docker run --rm \
                -v "$(pwd):/work" \
                "${IMAGE_NAME}" \
                sh -c 'find /work/packages -mindepth 2 -maxdepth 2 \( -name build -o -name dist -o -name packages \) -exec chmod -R u+rwX {} + 2>/dev/null || true; find /work/packages -mindepth 2 -maxdepth 2 \( -name build -o -name dist -o -name packages \) -exec rm -rf {} +; find /work/packages -mindepth 2 -maxdepth 2 -name "*.spec" -exec rm -f {} +'
        else
            echo "error: failed to remove package artifacts and Docker is not available for root cleanup" >&2
            exit 1
        fi
    fi
fi

if [[ "${CLEAN_DOCKER_IMAGE}" == true ]]; then
    if command -v docker >/dev/null 2>&1; then
        echo "==> Removing Docker image: ${IMAGE_NAME}"
        docker image rm -f "${IMAGE_NAME}" >/dev/null 2>&1 || true
    else
        echo "==> Docker not found; skipping Docker image cleanup"
    fi
fi

if [[ "${CLEAN_DOCKER_CACHE}" == true ]]; then
    if command -v docker >/dev/null 2>&1; then
        echo "==> Pruning Docker build cache"
        docker builder prune -af
    else
        echo "==> Docker not found; skipping Docker cache cleanup"
    fi
fi

echo "==> Clean complete"
