# Gerrit MCP Server Development Guide

## Overview
This document serves as the comprehensive guide for developing, testing, and maintaining the `gerrit-mcp-server`. It provides practical instructions for all stages of the development lifecycle.

## Development Environment

### Prerequisites
- Python 3.12+
- `pip`
- `virtualenv` (recommended)

### Setup
The project includes a build script that handles the creation of the virtual environment and installation of dependencies using `uv`.

1.  **Run the build script:**
    ```bash
    ./build-gerrit.sh
    ```
    This will create a virtual environment in `.venv` and install all necessary dependencies.

2.  **Activate the virtual environment:**
    ```bash
    source .venv/bin/activate
    ```

> [!IMPORTANT]
> **ALWAYS** use the virtual environment's Python. Never use the system Python.

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
Ensure your virtual environment is activated, then run:

```bash
./test.sh
```

## Runtime & Configuration

### Configuration
The server is configured via `gerrit_mcp_server/gerrit_config.json`.
- **Environment Variable:** `GERRIT_CONFIG_PATH` can be used to point to a custom config file.
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
To configure the Gemini CLI to use this server, see the **[Gemini CLI Setup Guide](docs/gemini-cli.md)**.

### Running Locally
To run the server locally for debugging (ensure venv is active):
```bash
python -m gerrit_mcp_server
```

## Debugging
- **Logs:** The server outputs logs to stderr.

## Contributing

### Creating a CL
This project uses Gerrit for code reviews. The primary development branch is `master`.

1.  **Create a new branch:**
    ```bash
    git checkout -b <your-feature-branch>
    ```
2.  **Commit your changes:**
    ```bash
    git commit -m "Your descriptive commit message"
    ```
3.  **Push for review:**
    Changes must be pushed to `refs/for/master` to create a CL. Direct pushes to `master` are not permitted.
    ```bash
    git push origin HEAD:refs/for/master
    ```
