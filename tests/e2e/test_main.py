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
import uuid
import pytest
from gerrit_mcp_server import main

# --- Fixtures ---

@pytest.fixture(scope="module")
def e2e_config():
    """
    Loads the E2E test configuration from a JSON file.
    Skips all tests in the module if the file is missing.
    """
    config_path = os.path.join(os.path.dirname(__file__), "e2e_config.json")
    if not os.path.exists(config_path):
        pytest.skip(
            "E2E config file 'tests/e2e/e2e_config.json' not found. "
            "Copy 'tests/e2e/e2e_config.sample.json' to create one.",
            allow_module_level=True
        )
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    return config

@pytest.fixture
def gerrit_base_url(e2e_config):
    return e2e_config.get("gerrit_base_url")

@pytest.fixture
def known_cl(e2e_config):
    return e2e_config.get("known_cl")

@pytest.fixture
def known_user(e2e_config):
    return e2e_config.get("known_user")

@pytest.fixture
def test_project(e2e_config):
    project = e2e_config.get("test_project")
    if not project:
        pytest.skip("Skipping write tests: 'test_project' not configured.")
    return project

@pytest.fixture
def test_reviewer(e2e_config):
    return e2e_config.get("test_reviewer")

@pytest.fixture
async def created_change(gerrit_base_url):
    """
    Yields a function that creates a change, and ensures it is abandoned during teardown.
    This acts as a context manager for the test data.
    """
    created_cl_ids = []

    async def _create(project, subject, branch="main"):
        result = await main.create_change(
            project=project,
            subject=subject,
            branch=branch,
            gerrit_base_url=gerrit_base_url,
        )
        # Extract the CL number to use for abandonment
        match = re.search(r"new change (\d+)", result[0]["text"])
        if match:
            created_cl_ids.append(match.group(1))
        return result, match.group(1) if match else None

    yield _create

    # Teardown: Abandon all created changes
    for cl_id in created_cl_ids:
        print(f"Cleaning up by abandoning CL {cl_id}...")
        try:
            await main.abandon_change(
                change_id=cl_id,
                gerrit_base_url=gerrit_base_url,
                message="Cleaning up after E2E test.",
            )
            print(f"CL {cl_id} abandoned.")
        except Exception as e:
            print(f"Failed to abandon CL {cl_id}: {e}")

# --- Read-Only Tests ---

@pytest.mark.asyncio
async def test_e2e_query_changes(gerrit_base_url):
    """Tests that we can query open changes from the Gerrit instance."""
    result = await main.query_changes(
        query="status:open", gerrit_base_url=gerrit_base_url, limit=5
    )
    assert "Found 5 changes" in result[0]["text"]

@pytest.mark.asyncio
async def test_e2e_get_change_details(gerrit_base_url, known_cl):
    """Tests that we can get the details of a known CL."""
    result = await main.get_change_details(
        change_id=known_cl, gerrit_base_url=gerrit_base_url
    )
    text = result[0]["text"]
    assert f"Summary for CL {known_cl}" in text
    assert "Subject:" in text

@pytest.mark.asyncio
async def test_e2e_list_change_files(gerrit_base_url, known_cl):
    """Tests that we can list the files of a known CL."""
    result = await main.list_change_files(
        change_id=known_cl, gerrit_base_url=gerrit_base_url
    )
    assert f"Files in CL {known_cl}" in result[0]["text"]

@pytest.mark.asyncio
async def test_e2e_get_most_recent_cl(gerrit_base_url, known_user):
    """Tests that we can get the most recent CL for a known user."""
    result = await main.get_most_recent_cl(
        user=known_user, gerrit_base_url=gerrit_base_url
    )
    text = result[0]["text"]
    # The test should pass if a CL is found OR if it correctly reports no changes.
    assert (
        f"Most recent CL for {known_user}" in text
        or f"No changes found for user: {known_user}" in text
    )

# --- Write Tests ---

@pytest.mark.asyncio
async def test_e2e_create_and_abandon_change(test_project, gerrit_base_url, created_change):
    """Tests the full lifecycle of creating and abandoning a change."""
    subject = f"E2E Test: Create and Abandon - {uuid.uuid4()}"
    
    # created_change fixture handles the creation and automatic cleanup (abandonment)
    result, cl_id = await created_change(project=test_project, subject=subject)
    
    assert "Successfully created new change" in result[0]["text"]
    assert cl_id is not None

    # Verify the creation was successful by fetching details
    details = await main.get_change_details(
        cl_id, gerrit_base_url=gerrit_base_url
    )
    assert subject in details[0]["text"]