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
`/plugins`, the Gerrit MCP tools are available, and `$gerrit:setup` can be
invoked explicitly when no configuration file exists. Use a temporary or test
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
  instance. They are opt-in and start an isolated Gerrit container by default.
  An explicit external-server mode is also available. They verify querying,
  change details, changed files, user queries, and creating/abandoning changes.

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

### Container-backed tests (default)

```bash
uv sync --extra dev
uv run pytest tests/e2e
```

Testcontainers starts the pinned `gerritcodereview/gerrit:3.13.10` image with a
fresh Gerrit site, provisions test data, and removes the container and its
anonymous volumes afterward, including when tests fail. No externally maintained
server or personal credentials are needed. Ordinary `uv run pytest` excludes E2E
tests and never starts Docker.

Requirements:

- Python 3.12+ and the development dependencies.
- Host `curl`, used by the server's real request path.
- A running local Docker daemon, with socket access for the test user.
- Registry access to pull the Gerrit image and Testcontainers' Ryuk cleanup
  image on first use. Subsequent runs can use cached images.

On Linux, the test user normally needs membership in the `docker` group; log out
and back in after changing membership. Docker socket access grants significant
privileges. Use trusted, dedicated development or CI machines.

The Gerrit HTTP port is dynamically allocated and bound to `127.0.0.1`.
Non-loopback container endpoints and remote Docker daemons are not supported.
Gerrit uses developer authentication and disposable test credentials, not a
production authentication configuration. Never expose this fixture publicly.

The fixture waits up to 180 seconds for authenticated REST readiness after the
container starts. Image download time is separate. An explicitly selected E2E
run fails if Docker, image pulls, initialization, or readiness fails; it does
not silently skip tests. Gerrit stdout/stderr is saved to
`.pytest_cache/e2e/gerrit-container.log`, including setup failures after
container creation. Override the artifact directory with
`--e2e-artifacts=<directory>`. Temporary MCP configuration overrides pytest's
test configuration only for the E2E session and is restored afterward. Container
mode also adds temporary loopback proxy exemptions for real `curl` requests;
external mode leaves proxy settings unchanged.

### Externally managed Gerrit

Copy `tests/e2e/e2e_config.sample.json` to the ignored
`tests/e2e/e2e_config.json`, then edit it for a dedicated test server:

```bash
uv run pytest tests/e2e --e2e-backend=external
# Alternatively, use a configuration outside the checkout:
uv run pytest tests/e2e --e2e-backend=external --e2e-config=/path/to/e2e.json
```

External mode does not start Docker or provision accounts, projects, or seed
changes. Missing required configuration is an error. Configure:

- `gerrit_base_url`: a reachable Gerrit URL. Non-loopback hosts must support
  HTTPS with a certificate trusted by host `curl`.
- `gerrit_config_path`: a separate MCP host/authentication configuration,
  following [the configuration guide](configuration.md). Its host entry must
  match the E2E URL, and its credentials must be valid for that server. Relative
  paths resolve against the E2E JSON file's directory; `~` is expanded. The
  default pytest authentication file is not sufficient for an external server.
- `known_cl`: a visible, open change with a current patch set containing at
  least one changed file other than `/COMMIT_MSG`. Use its numeric change
  number.
- `known_user`: an owner identifier accepted by Gerrit's `owner:` query, with at
  least one change visible to the configured account.
- `test_project`: optional dedicated non-production project for the write test.
  Leave it empty to run the four read-only tests and skip the write test.
- `test_branch`: an existing branch in that project; defaults to `main`.

> [!IMPORTANT] Setting `test_project` enables writes. The account needs
> permission to create changes on the selected branch and abandon its own
> changes. Do not point write tests at a production project. The test abandons
> its changes, including during failure cleanup, but abandoned changes remain on
> the external server. Cleanup failures are reported as test errors. The suite
> never deletes a project or modifies the configured known change.

Do not commit real E2E configuration or credentials. Different Gerrit
installations may have additional project policies that must permit the test's
REST change-creation workflow. The five core scenarios do not require task,
depends-on, or code-owners Gerrit plugins.

### Zuul

The separate `gerrit-mcp-run-e2e-tests` check job installs Docker using
`ensure-docker`, grants the test user Docker socket access, and runs the
container backend. CI nodes need privileges to install/start Docker, enough disk
and memory for Gerrit, and access to the Gerrit and Ryuk container registries.
The job's 30-minute timeout includes image downloads. Existing unit/integration
jobs are unchanged.

The E2E job publishes Gerrit logs and JUnit results under the build's `e2e/` log
directory, including on test failure. Locally, the equivalent command is:

```bash
uv run pytest tests/e2e --e2e-backend=container \
  --e2e-artifacts=e2e-results --junitxml=e2e-results/junit.xml
```

Future E2E coverage should exercise the MCP client/server transport and
additional tools and Gerrit plugins; the current suite calls tool
implementations directly while exercising real Gerrit REST requests through host
`curl`.
