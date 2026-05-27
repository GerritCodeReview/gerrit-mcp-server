# Gerrit MCP Server Development Guide

## Overview

This document serves as the comprehensive guide for developing, testing, and
maintaining the `gerrit-mcp-server`. It provides practical instructions for all
stages of the development lifecycle.

## Development Environment

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (the build
  script will install it via `pip` if absent)

### Setup

The project uses `uv` for dependency management. `uv.lock` is committed to the
repository to ensure reproducible installs.

1. **Run the build script:**

   ```bash
   ./build-gerrit.sh
   ```

   This will create a virtual environment in `.venv` and install all
   dependencies (including dev extras) via `uv sync`.

2. **Activate the virtual environment:**

   ```bash
   source .venv/bin/activate
   ```

> [!IMPORTANT] **ALWAYS** use the virtual environment's Python. Never use the
> system Python.

## Testing Standards

We use **pytest** as our testing framework.

### Structure

- **Files:** `test_*.py`
- **Functions:** Descriptive names like `test_query_changes_returns_results`.
- **Pattern:** Arrange, Act, Assert.

### Fixtures

- Use `pytest` fixtures for setup and dependency injection.
- Place shared fixtures in `conftest.py`.
- Use `unittest.mock.patch` as a context manager or fixture.

### Running Tests

Run tests from the project root (no venv activation needed):

```bash
uv run pytest
```

### Making any changes to source

If any changes to source are ever made, you must run `uv run pytest` to validate
that the changes did not break any tests. Ask the user first after any changes
are made.

## Code Style

Use the [`/astral:ruff` skill](https://github.com/astral-sh/claude-code-plugins)
if available. Otherwise, to fix and format:

```bash
uv run ruff check --fix . && uv run ruff format .
```

To check without modifying:
`uv run ruff check . && uv run ruff format --check .`

## Documentation

User-facing documentation lives in the `docs/` directory. Keep it in sync with
code changes — docs are part of the deliverable, not an afterthought.

### Layout

- **`docs/configuration.md`** — the `gerrit_config.json` schema and all
  authentication methods.
- **`docs/available_tools.md`** — every MCP tool exposed by the server and what
  it does.
- **`docs/testing.md`** — how to run unit, integration, and E2E tests.
- **`docs/best_practices.md`** — tips for using the server effectively.
- **`docs/use_cases.md`** — worked scenarios demonstrating the server.
- **`docs/gemini-cli.md`** — client setup for the Gemini CLI.
- **`docs/contributing.md`** / **`docs/code-of-conduct.md`** — contribution
  guidelines and community standards.

### When to update docs

- **Add or change a tool** → update `docs/available_tools.md`.
- **Change config structure or auth** → update `docs/configuration.md`.
- **Change how tests are run** → update `docs/testing.md`.
- **Change behavior users rely on** → check `docs/best_practices.md` and
  `docs/use_cases.md`.

### Adding, renaming, or removing a document

When you add, rename, or remove a file in `docs/`, cross-check the other
documentation files for references that need updating — in particular
`README.md` (which maintains its own index of doc links), `AGENTS.md`, and any
sibling docs that link to the changed file. Stale or broken cross-references
should be fixed in the same change.

### Style

Match the existing Markdown conventions: wrap prose at ~80 columns, use fenced
code blocks with language hints, and prefer `> [!IMPORTANT]`/`> [!NOTE]`
callouts as used elsewhere in this guide.

Enforce correct formatting by running mdformat before submitting:

```bash
uv run mdformat .
```

To check without modifying: `uv run mdformat --check .`

## Runtime & Configuration

### Configuration

The server is configured via `gerrit_mcp_server/gerrit_config.json`.

- **Environment Variable:** `GERRIT_CONFIG_PATH` can be used to point to a
  custom config file.
- **Structure:**
  ```json
  {
    "gerrit_hosts": [
      {
        "name": "MyGerrit",
        "external_url": "https://gerrit.example.com",
        "authentication": { "type": "http_basic", ... }
      }
    ]
  }
  ```
  *See [Configuration Guide](docs/configuration.md) for full details.*

### Client Setup (Gemini CLI)

To configure the Gemini CLI to use this server, see the
**[Gemini CLI Setup Guide](docs/gemini-cli.md)**.

### Running Locally

To run the server locally for debugging (no venv activation needed):

```bash
uv run gerrit-mcp-server
```

## Debugging

- **Logs:** The server outputs logs to stderr.

## Contributing

### Creating a CL

This project uses Gerrit for code reviews. The primary development branch is
`master`.

1. **Create a new branch:**
   ```bash
   git checkout -b <your-feature-branch>
   ```
2. **Commit your changes:**
   ```bash
   git commit -m "Your descriptive commit message"
   ```
3. **Push for review:** Changes must be pushed to `refs/for/master` to create a
   CL. Direct pushes to `master` are not permitted.
   ```bash
   git push origin HEAD:refs/for/master
   ```
