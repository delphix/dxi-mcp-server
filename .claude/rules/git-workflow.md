# Git Workflow Rules

## Branch Strategy

- `main` — stable release branch
- Feature branches off `main` — use `dlpx/pr/<username>/<description>` naming convention

## Pull Requests

This project uses GitHub PRs against the `delphix/dxi-mcp-server` repository.

When creating a PR, include:
- **What changed**: which tools, toolsets, or config files were modified
- **Why**: the DCT API or use case being addressed
- **Testing**: how it was verified (MCP client used, toolset tested, DCT version)

## Commit Format

```
<short imperative description of change>
```

Keep commits focused. Separate toolset config changes from code changes where possible.

## Do Not

- Do not force-push to `main`
- Do not commit `logs/`, `__pycache__/`, or `.env` files
- Do not commit real API keys or DCT credentials anywhere in the repo
