# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import re
import unittest
import uuid

from gerrit_mcp_server import main

# --- E2E Test Configuration ---
# IMPORTANT: Before running these tests, you must create a file named e2e_config.json
# in the tests/e2e/ directory. You can use e2e_config.sample.json as a template.
#
# This file contains credentials and settings for running tests against a live
# Gerrit instance. It is intentionally not checked into version control.


def load_e2e_config():
    """Loads the E2E test configuration from a JSON file."""
    config_path = os.path.join(os.path.dirname(__file__), "e2e_config.json")
    if not os.path.exists(config_path):
        return None
    with open(config_path, "r") as f:
        return json.load(f)


E2E_CONFIG = load_e2e_config()


@unittest.skipIf(
    E2E_CONFIG is None,
    "Please copy and update 'tests/e2e/e2e_config.sample.json' to 'tests/e2e/e2e_config.json' to run E2E tests.",
)
class TestGerritE2E(unittest.IsolatedAsyncioTestCase):
    """
    End-to-end tests for the Gerrit MCP server.
    """

    def setUp(self):
        self.gerrit_base_url = E2E_CONFIG.get("gerrit_base_url")
        self.known_cl = E2E_CONFIG.get("known_cl")
        self.known_user = E2E_CONFIG.get("known_user")
        self.test_project = E2E_CONFIG.get("test_project")
        self.test_reviewer = E2E_CONFIG.get("test_reviewer")
        self.test_cl_id = None

    async def asyncTearDown(self):
        if self.test_cl_id:
            print(f"Cleaning up by abandoning CL {self.test_cl_id}...")
            await main.abandon_change(
                change_id=self.test_cl_id,
                gerrit_base_url=self.gerrit_base_url,
                message="Cleaning up after E2E test.",
            )
            print(f"CL {self.test_cl_id} abandoned.")

    # --- Read-Only Tests ---

    async def test_e2e_query_changes(self):
        """Tests that we can query open changes from the Gerrit instance."""
        result = await main.query_changes(
            query="status:open", gerrit_base_url=self.gerrit_base_url, limit=5
        )
        self.assertIn("Found 5 changes", result[0]["text"])

    async def test_e2e_get_change_details(self):
        """Tests that we can get the details of a known CL."""
        result = await main.get_change_details(
            change_id=self.known_cl, gerrit_base_url=self.gerrit_base_url
        )
        self.assertIn(f"Summary for CL {self.known_cl}", result[0]["text"])
        self.assertIn("Subject:", result[0]["text"])

    async def test_e2e_list_change_files(self):
        """Tests that we can list the files of a known CL."""
        result = await main.list_change_files(
            change_id=self.known_cl, gerrit_base_url=self.gerrit_base_url
        )
        self.assertIn(f"Files in CL {self.known_cl}", result[0]["text"])

    async def test_e2e_get_most_recent_cl(self):
        """Tests that we can get the most recent CL for a known user."""
        result = await main.get_most_recent_cl(
            user=self.known_user, gerrit_base_url=self.gerrit_base_url
        )
        text = result[0]["text"]
        # The test should pass if a CL is found OR if it correctly reports no changes.
        self.assertTrue(
            f"Most recent CL for {self.known_user}" in text
            or f"No changes found for user: {self.known_user}" in text
        )

    # --- Write Tests ---

    @unittest.skipIf(
        not E2E_CONFIG or not E2E_CONFIG.get("test_project"),
        "Write tests are skipped because 'test_project' is not set in the config.",
    )
    async def test_e2e_create_and_abandon_change(self):
        """Tests the full lifecycle of creating and abandoning a change."""
        subject = f"E2E Test: Create and Abandon - {uuid.uuid4()}"
        result = await main.create_change(
            project=self.test_project,
            subject=subject,
            branch="main",
            gerrit_base_url=self.gerrit_base_url,
        )
        self.assertIn("Successfully created new change", result[0]["text"])

        # Extract the CL number to use for abandonment
        match = re.search(r"new change (\d+)", result[0]["text"])
        self.assertIsNotNone(match)
        self.test_cl_id = match.group(1)

        # The tearDown will handle the abandon operation.
        # We just need to verify the creation was successful.
        details = await main.get_change_details(
            self.test_cl_id, gerrit_base_url=self.gerrit_base_url
        )
        self.assertIn(subject, details[0]["text"])


if __name__ == "__main__":
    unittest.main()