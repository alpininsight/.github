# Organization GitHub Configuration

This directory contains organization-wide GitHub configurations.

## Labels

Labels are defined in `labels.yml` and automatically synced to all repositories.

### How it works

1. **Automatic sync on change**: When `labels.yml` is updated, the `sync-labels.yml` workflow runs and syncs to all repos
2. **Weekly sync**: Runs every Sunday at 00:00 UTC to catch new repositories
3. **Manual trigger**: Can be triggered manually from Actions tab with optional dry-run mode

### Adding/modifying labels

Edit `labels.yml` and commit. The workflow will automatically sync changes.

```yaml
- name: my-label
  color: "ff0000"  # hex color without #
  description: Label description
```

### Required setup

The workflow requires a Personal Access Token (PAT) with `repo` scope stored as organization secret:

1. Create a PAT at https://github.com/settings/tokens with `repo` scope
2. Add it as organization secret named `ORG_LABEL_SYNC_TOKEN`:
   - Go to Organization Settings → Secrets and variables → Actions
   - Add new organization secret

### Manual sync script

For one-time syncs or debugging, use the shell script:

```bash
# Dry run (show what would change)
./scripts/sync-labels-all-repos.sh --dry-run

# Actually sync
./scripts/sync-labels-all-repos.sh
```

Prerequisites:
- `gh` CLI authenticated
- `yq` installed (`brew install yq`)
