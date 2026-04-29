# Vision: DLPXECO-13635

## Problem Statement

Users who want to deploy the Delphix DCT MCP Server in containerised or cloud-native environments have no Docker image to pull — they must clone the repository, install Python 3.11+, and manage dependencies manually. This raises the deployment barrier for teams using Docker Compose, Kubernetes, or Windows environments where Python environment management is cumbersome. A first-class Docker image with clear README guidance removes this barrier and opens the server to a broader audience.

## Goals

- G1: Provide a production-ready `Dockerfile` that builds a portable image of the DCT MCP Server and runs correctly on both Linux and Windows Docker environments
- G2: Update `README.md` with a "Docker" section documenting how to build, configure, and run the server in a container, including how MCP clients connect to it
- G3: Include a placeholder registry URL in the README so that once the image is published to a container registry, users can `docker pull` it without cloning the repository
- G4: Ensure the Docker image passes the same functional smoke test (server starts, tools register) as the native Python setup

## Non-Goals

- NG1: Publishing or pushing the image to a public registry (Docker Hub, GitHub Container Registry, etc.) — the registry URL is a placeholder only; CI/CD publishing is out of scope for this ticket
- NG2: Kubernetes or Helm chart support — container orchestration beyond `docker run` and `docker-compose` is out of scope
- NG3: Changing the MCP server's core Python source code or tool behaviour — Docker packaging must not alter functionality
- NG4: Automated CI pipeline to rebuild the image on every commit — this ticket covers the Dockerfile and documentation only

## Success Criteria

- SC1: Running `docker build -t dct-mcp-server .` from the project root completes without error on a Linux host and on a Windows host with Docker Desktop
- SC2: Running `docker run --env DCT_API_KEY=... --env DCT_BASE_URL=... dct-mcp-server` starts the MCP server and the server prints its startup banner to stdout within 10 seconds
- SC3: The README `Docker` section contains step-by-step instructions that an engineer with no project knowledge can follow to build and run the container
- SC4: The README includes a placeholder registry pull command (e.g. `docker pull <registry-placeholder>/dct-mcp-server:latest`) that can be updated when the image is published

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| Vinay Byrappa (assignee) | Delivering the feature per ticket acceptance criteria |
| Platform/DevOps engineers | Ability to deploy MCP server via Docker without Python setup |
| Windows users | Running the MCP server without needing WSL or a Python environment |
| AI assistant users (Claude Desktop, Cursor, VS Code) | Connecting to a container-hosted MCP server via `port` config |
| Future CI/CD maintainers | A well-structured Dockerfile they can extend for registry publishing |

## Constraints

- Must use Python 3.11+ as the base image to match `pyproject.toml` requirement
- The Dockerfile must not require changes to the source Python code (`src/dct_mcp_server/`)
- Windows Docker compatibility requires using a Linux-based image (Windows containers are a separate, complex target — Linux image on Windows Docker Desktop is the standard approach)
- No new third-party Python dependencies may be added to `pyproject.toml` as part of this ticket
- The image must expose the server on a configurable port and accept all existing env vars (`DCT_API_KEY`, `DCT_BASE_URL`, `DCT_TOOLSET`, etc.) unchanged

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Layer size bloat from full Python image | Medium | Medium | Use `python:3.11-slim` base, add `.dockerignore` to exclude dev files, docs, logs, and venv |
| MCP stdio transport incompatible with Docker networking | Low | High | Server already supports both stdio (for MCP clients) and HTTP/port mode; document port-based connection in README |
| Windows Docker Desktop behavioural differences | Medium | Medium | Use Linux containers (the default Docker Desktop mode on Windows); explicitly document this in README |
| Credentials leaking into image layers via build args | Low | High | Document env vars as runtime flags (`-e` / `--env-file`) never as `ARG`/build-time bake-in; add note to README |
| Registry placeholder URL becoming stale | Low | Low | Mark it clearly as a placeholder with a TODO comment; document update process in README |
| uvx/uv not available in slim Docker image | Medium | Medium | Use `pip install` inside the Dockerfile rather than relying on `uvx`; this is the standard container approach |
