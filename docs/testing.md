# Testing the Gerrit MCP Server

This project includes a comprehensive test suite to ensure the server functions
correctly and remains stable. We use **pytest** as our testing framework.

## Quick Start

The easiest way to run the tests is to use `pytest` from the root of the project.

1.  **Build the Environment**:
    Run the build script to set up the virtual environment and install
    dependencies:
    ```bash
    ./build-gerrit.sh
    ```

2.  **Activate Virtual Environment**:
    ```bash
    source .venv/bin/activate
    ```

3.  **Run Tests**:
    ```bash
    pytest
    ```

## Test Structure

The tests are organized as follows:

*   `tests/unit/`: **Fast, isolated tests.** These tests verify individual
    functions and classes in isolation. External dependencies like `curl` and
    file system operations are mocked to ensure speed and determinism. They are
    the first line of defense.
*   `tests/integration/`: **Component interaction tests.** These tests verify
    that different parts of the application work together correctly. While they
    still mock external network calls (to avoid flakiness), they test the flow
    of data through the system, including configuration loading and command
    execution logic.
*   `tests/e2e/`: **End-to-End tests.** These tests run against a live Gerrit
    instance. They are optional and require specific configuration. They verify
    that the server can actually communicate with a real Gerrit server and
    perform actions like querying changes and posting comments.

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
pytest tests/e2e
```
