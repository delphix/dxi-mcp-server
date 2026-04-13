# Git Workflow Rules

## Branch Strategy

- `main` — stable release branch
- Feature branches use `dlpx/pr/<username>/<description>` naming convention

## Pull Request Workflow

**When raising a PR during `feature-implement`:**

1. Record the current branch as `$BASE_BRANCH` before making any commits:
   ```bash
   BASE_BRANCH=$(git branch --show-current)
   ```

2. Create a new feature branch off `$BASE_BRANCH`:
   ```bash
   git checkout -b dlpx/pr/<git-username>/<ticket-or-description>
   ```
   Use the git username from `git config user.name` (lowercased, spaces replaced with hyphens).

3. Commit changes on the new feature branch.

4. Push the feature branch and open the PR **against `$BASE_BRANCH`** (not `main`):
   ```bash
   git push -u origin dlpx/pr/<username>/<description>
   gh pr create --base "$BASE_BRANCH" --head dlpx/pr/<username>/<description> ...
   ```

This project uses GitHub PRs against the `delphix/dxi-mcp-server` repository.

When creating a PR, include:
- **What changed**: which tools, toolsets, or config files were modified
- **Why**: the DCT API or use case being addressed
- **Testing**: how it was verified (MCP client used, toolset tested, DCT version, startup path used)

## Commit Format

```
<short imperative description of change>
```

Keep commits focused. Separate toolset config changes from code changes where possible.

## Do Not

- Do not force-push to `main`
- Do not commit `logs/`, `__pycache__/`, or `.env` files
- Do not commit real API keys or DCT credentials anywhere in the repo
