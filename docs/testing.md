# Testing the Gerrit MCP Server

This project includes a comprehensive test suite to ensure the server functions
correctly and remains stable. We use **pytest** as our testing framework.

## Quick Start

Run tests from the project root (no venv activation needed):

```bash
uv run pytest
```

If you haven't run `./build-gerrit.sh` yet, `uv run` will set up the virtual
environment automatically on first use.

## Plugin Artifact Tests

The integration test `tests/integration/test_plugin_package.py` validates the
installable Claude Code artifacts without launching Claude Code. It checks the
plugin manifest, marketplace entry, MCP launch configuration, skill metadata,
and the configuration hook's JSON output and exit-code behavior.

Run it directly with:

```bash
uv run pytest tests/integration/test_plugin_package.py
```

The hook tests run the real `hooks/check-config.sh` script and replace only its
external `uv` invocation with a controlled test command. This keeps the tests
deterministic while checking the paths, environment, output, and status that the
client observes.

## Claude Code Smoke Test

The automated tests do not launch a Claude Code client. For a manual plugin
smoke test, load the repository directly:

```bash
claude --plugin-dir <path-to-gerrit-mcp-server>
```

In the new session, verify that the `gerrit` MCP tools are available and that
`/gerrit:setup` is offered when no configuration file exists. Use a temporary or
test configuration rather than production credentials when exercising the setup
flow.

## Codex Plugin Smoke Test

The automated tests also validate the portable Codex plugin manifest, MCP
configuration, native plugin paths, and explicit-only setup policy. They do not
launch Codex or modify the user's plugin configuration.

For a manual local smoke test, add the repository or its marketplace to Codex:

```bash
codex plugin marketplace add <path-to-gerrit-mcp-server>
codex plugin list --available --json
codex plugin add gerrit@gerrit-mcp --json
```

Start a new Codex session after installation. Verify that the plugin appears in
`/plugins`, the Gerrit MCP tools are available, and `$setup` can be invoked
explicitly when no configuration file exists. Use a temporary or test
configuration rather than production credentials.

## Test Structure

The tests are organized as follows:

- `tests/unit/`: **Fast, isolated tests.** These tests verify individual
  functions and classes in isolation. External dependencies like `curl` and file
  system operations are mocked to ensure speed and determinism. They are the
  first line of defense.
- `tests/integration/`: **Component interaction tests.** These tests verify that
  different parts of the application work together correctly. While they still
  mock external network calls (to avoid flakiness), they test the flow of data
  through the system, including configuration loading and command execution
  logic.
- `tests/e2e/`: **End-to-End tests.** These tests run against a live Gerrit
  instance. They are optional and require specific configuration. They verify
  that the server can actually communicate with a real Gerrit server and perform
  actions like querying changes and posting comments.

## Writing Tests

Tests should be simple, readable, and follow the "Arrange, Act, Assert" pattern.
We use `pytest` fixtures for setup and dependency injection.

### Example: Unit Test

```python
import pytest
from unittest.mock import patch
from gerrit_mcp_server import main

@pytest.mark.asyncio
async def test_get_bugs_from_cl():
    """The hero finds the bugs hidden in the message."""
    with patch("gerrit_mcp_server.main.run_curl") as mock_run_curl:
        mock_run_curl.return_value = '{"message": "Fixes: b/12345"}'
        result = await main.get_bugs_from_cl("123")
        assert "Found bug(s): 12345" in result[0]["text"]
```

## End-to-End (E2E) Tests

To run E2E tests, you need a `tests/e2e/e2e_config.json` file (see
`tests/e2e/e2e_config.sample.json`).

**Note:** This configuration file is **required** for E2E tests to know which
Gerrit instance to target and what credentials to use.

Run them with:

```bash
uv run pytest tests/e2e
```
