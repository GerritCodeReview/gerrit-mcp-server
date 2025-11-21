## 🧪 Testing

This project includes a suite of unit and integration tests to ensure the server
functions correctly. The following commands should be run from the root of the
`gerrit` project.

### Running the Tests

1.  **Set up the test environment and install dependencies (if not already done):**
    ```bash
    ./build-gerrit.sh
    ```
2.  **Run the tests:**
    ```bash
    ./test.sh
    ```

This command will discover and run all tests in the `tests` directory.

### Making any changes to source

If any changes to source are ever made, you must run `./test.sh` to validate
that the changes did not break any tests. Ask the user first after any changes
are made.
