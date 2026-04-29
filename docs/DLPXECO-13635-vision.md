# Vision: DLPXECO-13635

## Problem Statement

Users and operators of the Delphix DCT MCP Server currently must run the server directly on a host machine by cloning the repository and executing shell scripts or installing via pip/uvx. There is no containerised packaging, which makes deployment inconsistent across environments (especially Windows), complicates onboarding, and prevents deployment in container-native infrastructure. Without a Docker image, teams cannot quickly spin up the MCP server in isolated, reproducible environments, and cross-platform support (particularly Windows) is difficult to guarantee.

## Goals

- G1: Provide a working `Dockerfile` that builds a Docker image capable of running the DCT MCP Server on Linux and Windows container hosts
- G2: Publish a `docker-compose.yml` (or equivalent) that allows operators to start the server with a single command without needing to understand internal dependencies
- G3: Document how to build, configure, and run the MCP server via Docker in the README, covering both Linux and Windows instructions
- G4: Include a placeholder repository URL (e.g. Docker Hub, GitHub Container Registry) where the official Docker image will be hosted once published

## Non-Goals

- NG1: This release does not include CI/CD pipeline automation to build and push the Docker image to a registry (tracked separately)
- NG2: Does not change the server's internal code, transport, or configuration logic — purely packaging and documentation
- NG3: Does not provide Windows-native (non-WSL) Docker daemon setup instructions — assumes Docker Desktop is already installed on Windows

## Success Criteria

- SC1: A `Dockerfile` exists at the repository root and `docker build -t dct-mcp-server .` completes without errors on Linux
- SC2: The built Docker image starts the MCP server process correctly and the server is accessible via the configured port
- SC3: The README contains a clearly labelled Docker section with step-by-step instructions for Linux and Windows users
- SC4: A placeholder Docker image URL is present in README (clearly marked as "coming soon" or equivalent)
- SC5: The Docker image passes basic connectivity smoke test (server starts, responds to health check or MCP protocol init)

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| End users (AI assistant operators) | Faster, more reliable deployment of the MCP server without manual environment setup |
| Windows users | Ability to run the server on Windows via Docker Desktop without WSL complexity |
| Platform / DevOps teams | Container-native deployment that fits standard infrastructure workflows |
| Delphix maintainers | Reduced support burden from environment-related setup issues |

## Constraints

- The Docker image must work on both Linux and Windows (via Docker Desktop for Windows with Linux containers)
- No new runtime dependencies may be added to the server itself — Docker packaging only
- The Dockerfile must respect the existing Python 3.11 requirement
- Must use an official, non-deprecated base image (e.g. `python:3.11-slim`) to avoid supply-chain risks
- The placeholder Docker image URL must be clearly marked as a placeholder — not a live, pullable image

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Docker image fails to work on Windows due to line-ending or path issues in startup scripts | Medium | High | Use POSIX-safe startup commands in Dockerfile; test on Windows Docker Desktop |
| Base image introduces known CVEs | Low | Medium | Pin to a specific digest or use regularly-scanned slim variant; document image update process |
| MCP stdio transport behaves differently inside a container (signal handling, stdin/stdout buffering) | Low | High | Test MCP client connection to containerised server end-to-end; document any required Docker flags (e.g. `-i` for stdin) |
| README instructions become stale when Docker commands or image names change | Medium | Low | Use a single source-of-truth section in README; add note to keep placeholder URL updated when registry is confirmed |
| Windows users confused by Linux-container vs Windows-container distinction | Medium | Medium | Explicitly state "Linux containers mode required" in Windows instructions; include Docker Desktop config note |
