# 🐍 Gerrit MCP Server

An MCP (Model Context Protocol) server for interacting with the Gerrit code
review system. This server allows a language model like Gemini to query changes,
retrieve details, and manage reviews by executing `curl` commands against the
Gerrit REST API.

This server can be run as a persistent **HTTP server** or on-demand via **STDIO**.

## 📚 Documentation

For detailed information, please see the documents in the `docs/` directory:

*   **[Configuration](docs/configuration.md)**: A detailed guide to the `gerrit_config.json` file and all authentication methods.
*   **[Testing Guide](docs/testing.md)**: Instructions on how to run the unit, integration, and E2E tests.
*   **[Gemini CLI Setup](docs/gemini-cli.md)**: How to configure the Gemini CLI to use this server.
*   **[Best Practices](docs/best_practices.md)**: Tips for using the server effectively.
*   **[Contributing](docs/contributing.md)**: Guidelines for contributing to the project.
*   **[Available Tools](docs/available_tools.md)**: A list of all available tools and their descriptions.
*   **[Example Use Cases](docs/use_cases.md)**: Scenarios demonstrating how to use the server.

## 🚀 Getting Started

### 1. Prerequisites

Before you begin, ensure you have the following tools installed and available in
your system's `PATH`.

*   **Python 3.11+**: The build script requires a modern version of Python.
*   **curl**: The standard command-line tool for transferring data with URLs.

*   **Project Changes**: [View on Gerrit](https://gerrit-review.googlesource.com/q/project:gerrit-mcp-server)
*   **Source Hosting**: [View on Gerrit Code](https://gerrit.googlesource.com/gerrit-mcp-server)

### 2. Build the Environment

Run the build script from the root of the `gerrit-mcp-server` project directory.
This will create a Python virtual environment, install all dependencies, and
make the server ready to run.

```bash
./build-gerrit.sh
```

### 3. Configure the Server

You will need to create a `gerrit_config.json` file inside the
`gerrit_mcp_server` directory. Copy the provided sample file
`gerrit_mcp_server/gerrit_config.sample.json` and customize it for your
environment. See the **[Configuration Guide](docs/configuration.md)** for
details on all available options.

```bash
cp gerrit_mcp_server/gerrit_config.sample.json gerrit_mcp_server/gerrit_config.json
```

### 4. Run the Server (HTTP Mode)

To run the server as a persistent background process, use the `server.sh` script:

*   **Start the server:**
    ```bash
    ./server.sh start
    ```
*   **Check the status:**
    ```bash
    ./server.sh status
    ```
*   **Stop the server:**
    ```bash
    ./server.sh stop
    ```

For on-demand STDIO mode, please see the **[Gemini CLI Setup Guide](docs/gemini-cli.md)**.


### Security

This is not an officially supported Google product. This project is not
eligible for the [Google Open Source Software Vulnerability Rewards
Program](https://bughunters.google.com/open-source-security).
