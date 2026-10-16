#!/usr/bin/env bash
# Build the application, build and tag a Docker image, and push it to Docker Hub.
#
# Required environment variables:
#   DH_USERNAME   Docker Hub username (also used to form the default image name)
#   DH_PASSWORD   Docker Hub password or access token
#
# Optional environment variables:
#   IMAGE_NAME          Full image repository name (default: $DH_USERNAME/flexget)
#   IMAGE_TAG           Primary tag to apply (default: current version from flexget/_version.py)
#   V2_WEBUI_LOCATION   URL or local file path for the v2 WebUI dist.zip (default: latest GitHub release)

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# --- Load .env if present (does not overwrite variables already set in the environment) ---
if [[ -f .env ]]; then
    while IFS='=' read -r key value; do
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        [[ -v "$key" ]] && continue
        export "$key=$value"
    done < .env
fi

# --- Validate required variables ---
: "${DH_USERNAME:?DH_USERNAME is required}"
: "${DH_PASSWORD:?DH_PASSWORD is required}"

# --- Resolve defaults ---
IMAGE_NAME="${IMAGE_NAME:-${DH_USERNAME}/flexget}"
IMAGE_TAG="${IMAGE_TAG:-$(uv run scripts/dev_tools.py version)}"

echo "==> Image:  ${IMAGE_NAME}:${IMAGE_TAG}"

# --- Step 1: Build the application ---
echo "==> Building application..."
uv build

# --- Step 2: Build the Docker image ---

# If V2_WEBUI_LOCATION is a local path, copy it into the build context so that
# Docker's ADD picks it up at /flexget/webui-dist.zip during the bundle step.
DOCKER_V2_WEBUI_LOCATION="${V2_WEBUI_LOCATION:-}"
WEBUI_DIST_COPIED=false

if [[ -n "${V2_WEBUI_LOCATION:-}" && ! "$V2_WEBUI_LOCATION" =~ ^https?:// ]]; then
    EXPANDED_PATH="${V2_WEBUI_LOCATION/#\~/$HOME}"
    cp "$EXPANDED_PATH" ./webui-dist.zip
    WEBUI_DIST_COPIED=true
    DOCKER_V2_WEBUI_LOCATION=/flexget/webui-dist.zip
fi

cleanup() {
    [[ "$WEBUI_DIST_COPIED" == true ]] && rm -f ./webui-dist.zip
}
trap cleanup EXIT

echo "==> Building Docker image..."
docker build \
    ${DOCKER_V2_WEBUI_LOCATION:+--build-arg "V2_WEBUI_LOCATION=${DOCKER_V2_WEBUI_LOCATION}"} \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -t "${IMAGE_NAME}:latest" \
    .

# --- Step 3: Push to Docker Hub ---
echo "==> Logging in to Docker Hub..."
echo "${DH_PASSWORD}" | docker login -u "${DH_USERNAME}" --password-stdin

echo "==> Pushing ${IMAGE_NAME}:${IMAGE_TAG}..."
docker push "${IMAGE_NAME}:${IMAGE_TAG}"
docker push "${IMAGE_NAME}:latest"

docker logout

echo ""
echo "Done. Pushed ${IMAGE_NAME}:${IMAGE_TAG} and ${IMAGE_NAME}:latest"
