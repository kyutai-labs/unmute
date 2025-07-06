#!/usr/bin/env bash

# Update Kubernetes manifests with dynamic image names
# This script detects the repository owner and updates all image references

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$SCRIPT_DIR"

# Function to get repository owner from git remote
get_repo_owner() {
    local repo_url=$(git config --get remote.origin.url 2>/dev/null || echo "")
    if [ -z "$repo_url" ]; then
        echo -e "${RED}Error: Could not determine repository owner from git remote.${NC}"
        echo "Please run this script from within the git repository."
        exit 1
    fi

    # Extract owner from various URL formats
    # GitHub SSH: git@github.com:owner/repo.git
    # GitHub HTTPS: https://github.com/owner/repo.git
    local owner
    if [[ "$repo_url" =~ github\.com[:/]([^/]+)/([^/]+)(\.git)?$ ]]; then
        owner="${BASH_REMATCH[1]}"
    else
        echo -e "${RED}Error: Could not parse repository owner from URL: $repo_url${NC}"
        exit 1
    fi

    # Convert to lowercase for container registry compatibility
    echo "$owner" | tr '[:upper:]' '[:lower:]'
}

# Function to update image references in a file
update_image_refs() {
    local file="$1"
    local repo_owner="$2"

    if [ ! -f "$file" ]; then
        echo -e "${YELLOW}Warning: File $file not found, skipping.${NC}"
        return
    fi

    echo -e "${GREEN}Updating image references in $file...${NC}"

    # Update backend image
    sed -i "s|image: ghcr\.io/[^/]*/unmute-backend:latest|image: ghcr.io/$repo_owner/unmute-backend:latest|g" "$file"

    # Update frontend image
    sed -i "s|image: ghcr\.io/[^/]*/unmute-frontend:latest|image: ghcr.io/$repo_owner/unmute-frontend:latest|g" "$file"

    # Update moshi-server image
    sed -i "s|image: ghcr\.io/[^/]*/moshi-server:latest|image: ghcr.io/$repo_owner/moshi-server:latest|g" "$file"

    echo -e "${GREEN}✓ Updated $file${NC}"
}

# Main execution
echo -e "${GREEN}Detecting repository owner...${NC}"
REPO_OWNER=$(get_repo_owner)
echo -e "${GREEN}Repository owner: $REPO_OWNER${NC}"

echo -e "${GREEN}Updating Kubernetes manifests...${NC}"

# Update all relevant files
update_image_refs "$K8S_DIR/backend.yaml" "$REPO_OWNER"
update_image_refs "$K8S_DIR/frontend.yaml" "$REPO_OWNER"
update_image_refs "$K8S_DIR/tts.yaml" "$REPO_OWNER"
update_image_refs "$K8S_DIR/stt.yaml" "$REPO_OWNER"

echo -e "${GREEN}✓ All image references updated successfully!${NC}"
echo -e "${GREEN}Images will be pulled from: ghcr.io/$REPO_OWNER/${NC}"
echo ""
echo -e "${YELLOW}Note: Make sure the images are built and pushed to GHCR before deploying.${NC}"
echo -e "${YELLOW}You can check the GitHub Actions workflow status with: gh run list${NC}"
