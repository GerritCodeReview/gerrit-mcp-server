# 🐍 Gerrit MCP Server

An MCP (Model Context Protocol) server that brings Gerrit code-review workflows
to AI clients including the Gemini CLI, Claude Code, and OpenAI Codex. It
provides tools to search changes, inspect diffs and review metadata, manage
reviewers, comments, and change state, and analyze related or dependent changes.
Optional extensions add tools backed by Gerrit plugins.

Use it as a **Gemini CLI extension**, **Claude Code plugin**, or **Codex
plugin**, or run it directly as a persistent **HTTP server** or on-demand via
**STDIO**.

## 📚 Documentation

For detailed information, please see the documents in the `docs/` directory:

- **[Configuration](docs/configuration.md)**: A detailed guide to the
  `gerrit_config.json` file and all authentication methods.
- **[Testing Guide](docs/testing.md)**: Instructions on how to run the unit,
  integration, and E2E tests.
- **[Gemini CLI Setup](docs/gemini-cli.md)**: How to configure the Gemini CLI to
  use this server.
- **[Claude Code Setup](docs/claude-code.md)**: How to use this server as a
  Claude Code plugin.
- **[Codex Setup](docs/codex.md)**: How to use this server as a Codex plugin.
- **[Best Practices](docs/best_practices.md)**: Tips for using the server
  effectively.
- **[Contributing](docs/contributing.md)**: Guidelines for contributing to the
  project.
- **[Available Tools](docs/available_tools.md)**: A list of all available tools
  and their descriptions.
- **[Extensions](docs/extensions.md)**: How to register additional MCP tools
  without modifying the core server.
- **[Example Use Cases](docs/use_cases.md)**: Scenarios demonstrating how to use
  the server.

## 🚀 Getting Started

### 1. Prerequisites

Before you begin, ensure you have the following tools installed and available in
your system's `PATH`.

- **Python 3.12+**: Required by the server.
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)**: Used for
  dependency management and running the server. Optional — the build script will
  install it via `pip` if absent.
- **curl**: The standard command-line tool for transferring data with URLs.

### 2. Build the Environment

Run the build script from the root of the `gerrit-mcp-server` project directory.
This will create a virtual environment in `.venv` via `uv sync` and install all
dependencies.

```bash
./build-gerrit.sh
```

### 3. Configure the Server

Create the shared user config file described in the
**[Configuration Guide](docs/configuration.md)**. Copy the sample to the default
location (using the project virtual environment's Python):

```bash
config_path=$(uv run python -c 'from platformdirs import user_config_path; print(user_config_path("gerrit-mcp") / "gerrit_config.json")')
mkdir -p "$(dirname "$config_path")"
cp gerrit_mcp_server/gerrit_config.sample.json "$config_path"
```

Customize it for your environment. `GERRIT_CONFIG_PATH` overrides the default.
Existing repo-local configs must be moved or explicitly selected with that
variable; they are not migrated automatically.

Alternatively, if your harness supports skills (tested with Claude Code), the
`/gerrit:setup` skill can create or repair this file for you interactively. See
**[Interactive Setup](docs/configuration.md#interactive-setup-gerritsetup)**.

### 4. Run the Server (HTTP Mode)

To run the server as a persistent background process, use the `server.sh`
script:

- **Start the server:**
  ```bash
  ./server.sh start
  ```
- **Check the status:**
  ```bash
  ./server.sh status
  ```
- **Stop the server:**
  ```bash
  ./server.sh stop
  ```

For on-demand STDIO mode or client-specific installation instructions, see the
**[Gemini CLI Setup Guide](docs/gemini-cli.md)**,
**[Claude Code Setup Guide](docs/claude-code.md)**, or
**[Codex Setup Guide](docs/codex.md)**.

### Security

This is not an officially supported Google product. This project is not eligible
for the
[Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).
