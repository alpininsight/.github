#!/usr/bin/env bash
# Sync organization labels to all existing repositories
# Usage: ./scripts/sync-labels-all-repos.sh [--dry-run]
#
# Prerequisites:
#   - gh CLI authenticated with appropriate permissions
#   - yq installed (for YAML parsing)

set -euo pipefail

ORG="alpininsight"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
LABELS_FILE="$REPO_ROOT/.github/labels.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--dry-run]"
            echo ""
            echo "Options:"
            echo "  --dry-run, -n  Show what would be done without making changes"
            echo "  --help, -h     Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check prerequisites
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: gh CLI not found. Install from https://cli.github.com/${NC}"
    exit 1
fi

if ! command -v yq &> /dev/null; then
    echo -e "${RED}Error: yq not found. Install with: brew install yq${NC}"
    exit 1
fi

if [ ! -f "$LABELS_FILE" ]; then
    echo -e "${RED}Error: Labels file not found: $LABELS_FILE${NC}"
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: gh CLI not authenticated. Run: gh auth login${NC}"
    exit 1
fi

echo -e "${BLUE}========================================"
echo "Organization Label Sync"
echo "========================================${NC}"
echo ""
echo "Organization: $ORG"
echo "Labels file:  $LABELS_FILE"
echo "Dry run:      $DRY_RUN"
echo ""

# Get all repositories
echo -e "${BLUE}Fetching repositories...${NC}"
repos=$(gh repo list "$ORG" --no-archived --source --json name --limit 100 -q '.[].name')
repo_count=$(echo "$repos" | wc -l | tr -d ' ')
echo "Found $repo_count repositories"
echo ""

# Read labels from YAML into arrays
echo -e "${BLUE}Reading label definitions...${NC}"
label_count=$(yq e 'length' "$LABELS_FILE")
echo "Found $label_count labels to sync"
echo ""

# Extract labels into a temp file for easier processing
TEMP_LABELS=$(mktemp)
trap "rm -f $TEMP_LABELS" EXIT

yq e '.[] | .name + "|" + .color + "|" + .description' "$LABELS_FILE" > "$TEMP_LABELS"

# Process each repository
success_count=0
error_count=0

for repo in $repos; do
    echo -e "${YELLOW}----------------------------------------${NC}"
    echo -e "${YELLOW}Repository: $ORG/$repo${NC}"
    echo -e "${YELLOW}----------------------------------------${NC}"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}[DRY RUN] Would sync $label_count labels${NC}"
        ((success_count++))
        continue
    fi

    # Get existing labels
    existing_labels=$(gh label list --repo "$ORG/$repo" --json name -q '.[].name' 2>/dev/null || echo "")

    # Track errors for this repo
    repo_errors=0

    # Process each label
    while IFS='|' read -r name color description; do
        # Skip empty lines
        [ -z "$name" ] && continue

        # Check if label exists
        if echo "$existing_labels" | grep -qx "$name"; then
            # Update existing label
            if gh label edit "$name" \
                --repo "$ORG/$repo" \
                --color "$color" \
                --description "$description" 2>/dev/null; then
                echo -e "  ${GREEN}✓${NC} Updated: $name"
            else
                echo -e "  ${RED}✗${NC} Failed to update: $name"
                ((repo_errors++))
            fi
        else
            # Create new label
            if gh label create "$name" \
                --repo "$ORG/$repo" \
                --color "$color" \
                --description "$description" 2>/dev/null; then
                echo -e "  ${GREEN}✓${NC} Created: $name"
            else
                echo -e "  ${RED}✗${NC} Failed to create: $name"
                ((repo_errors++))
            fi
        fi
    done < "$TEMP_LABELS"

    if [ $repo_errors -eq 0 ]; then
        echo -e "  ${GREEN}Repository complete${NC}"
        ((success_count++))
    else
        echo -e "  ${RED}Repository had $repo_errors errors${NC}"
        ((error_count++))
    fi
done

# Summary
echo ""
echo -e "${BLUE}========================================"
echo "Summary"
echo "========================================${NC}"
echo -e "Repositories processed: $repo_count"
echo -e "Successful:            ${GREEN}$success_count${NC}"
echo -e "With errors:           ${RED}$error_count${NC}"

if [ $error_count -gt 0 ]; then
    exit 1
fi
