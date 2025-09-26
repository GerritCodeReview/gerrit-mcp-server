# Testing the Gerrit MCP Server

This project includes a comprehensive test suite to ensure the server functions correctly and remains stable. The tests are divided into three categories: unit, integration, and end-to-end (E2E).

## Running the Tests

The easiest way to run the core test suite is to use the provided script from the root of the `gerrit-mcp-server` project directory.

Before running the tests for the first time, you must build the environment:
```bash
./build-gerrit.sh
```

Once the environment is built, you can run the tests:
```bash
./test.sh
```

This command will automatically:
1.  Activate the Python virtual environment (`.venv`).
2.  Discover and run all **unit tests** located in `tests/unit/`.
3.  Discover and run all **integration tests** located in `tests/integration/`.

## Test Structure

The tests are organized as follows:

*   `tests/unit/`: These tests are designed to be fast and isolated. They test individual functions and classes without making any real network requests. Dependencies like `curl` are mocked to ensure predictable behavior.
*   `tests/integration/`: These tests verify that different parts of the server work together correctly. For example, the `test_build_and_run.py` test simulates the entire build and server startup process in a temporary directory to ensure the scripts are working as expected.
*   `tests/e2e/`: These are optional, manually-run tests that make real network requests to a live Gerrit instance.

## End-to-End (E2E) Tests

The E2E tests are designed to verify the server's functionality against a real, live Gerrit instance. They are not run by default.

### Running the E2E Tests

To run the E2E test suite, use the `--e2e` flag with the test script:

```bash
./test.sh --e2e
```

### E2E Prerequisites

Before running the E2E tests, you must configure the following:

*   **Main Configuration**: Ensure you have a valid `gerrit_mcp_server/gerrit_config.json`. Your E2E tests will authenticate using the methods defined in this file. See the **[Configuration Guide](configuration.md)** for details.

*   **E2E Test Data**: You must create a `tests/e2e/e2e_config.json` file. A template is provided at `tests/e2e/e2e_config.sample.json`. This file tells the test suite which Gerrit instance to target and what data to use for read-only tests.

    ```bash
    cp tests/e2e/e2e_config.sample.json tests/e2e/e2e_config.json
    ```

    Fill in the values in your new `e2e_config.json`:
    *   `gerrit_base_url`: The URL of the Gerrit instance to test against. This must match a host defined in your main `gerrit_config.json`.
    *   `known_cl`: A known, public CL number for read-only tests.
    *   `known_user`: A known user for user-specific queries.
    *   `test_project`: **(Optional)** A project where you have permission to create changes. If this is not set, write tests (like creating a new CL) will be skipped.
    *   `test_reviewer`: **(Optional)** A user you can add as a reviewer during write tests.
