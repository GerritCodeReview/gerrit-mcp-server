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

import re
import uuid

import pytest

from gerrit_mcp_server import main

# --- Fixtures ---


@pytest.fixture
async def created_change(gerrit_base_url):
    """
    Yields a function that creates a change, and ensures it is abandoned
    during teardown. This acts as a context manager for the test data.
    """
    created_cl_ids = set()

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
            created_cl_ids.add(match.group(1))
        return result, match.group(1) if match else None

    def _finished(cl_id):
        created_cl_ids.discard(cl_id)

    yield _create, _finished

    # Teardown: Abandon all created changes
    for cl_id in created_cl_ids:
        print(f"Cleaning up by abandoning CL {cl_id}...")
        try:
            result = await main.abandon_change(
                change_id=cl_id,
                gerrit_base_url=gerrit_base_url,
                message="Cleaning up after E2E test.",
            )
            print(f"CL {cl_id} abandoned.")
            assert "Successfully abandoned" in result[0]["text"]
        except Exception as e:
            pytest.fail(f"Failed to clean up CL {cl_id}: {e}")


# --- Read-Only Tests ---


@pytest.mark.asyncio
async def test_e2e_query_changes(gerrit_base_url, known_cl):
    """Tests that we can query open changes from the Gerrit instance."""
    result = await main.query_changes(
        query=f"change:{known_cl} status:open", gerrit_base_url=gerrit_base_url, limit=1
    )
    assert "Found 1 changes" in result[0]["text"]
    assert f"- {known_cl}:" in result[0]["text"]


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
    text = result[0]["text"]
    assert f"Files in CL {known_cl}" in text
    assert any(line.startswith("[") for line in text.splitlines()[1:])


@pytest.mark.asyncio
async def test_e2e_get_most_recent_cl(gerrit_base_url, known_user):
    """Tests that we can get the most recent CL for a known user."""
    result = await main.get_most_recent_cl(
        user=known_user, gerrit_base_url=gerrit_base_url
    )
    text = result[0]["text"]
    assert f"Most recent CL for {known_user}" in text
    assert re.search(r"- (?:\[WIP\] )?\d+:", text)


# --- Write Tests ---


@pytest.mark.asyncio
async def test_e2e_create_and_abandon_change(
    test_project, test_branch, gerrit_base_url, created_change
):
    """Tests the full lifecycle of creating and abandoning a change."""
    subject = f"E2E Test: Create and Abandon - {uuid.uuid4()}"

    # created_change fixture handles the creation and automatic cleanup (abandonment)
    create, finished = created_change
    result, cl_id = await create(
        project=test_project, subject=subject, branch=test_branch
    )

    assert "Successfully created new change" in result[0]["text"]
    assert cl_id is not None

    # Verify the creation was successful by fetching details
    details = await main.get_change_details(cl_id, gerrit_base_url=gerrit_base_url)
    assert subject in details[0]["text"]

    abandoned = await main.abandon_change(cl_id, gerrit_base_url=gerrit_base_url)
    assert "Successfully abandoned" in abandoned[0]["text"]
    finished(cl_id)
    details = await main.get_change_details(cl_id, gerrit_base_url=gerrit_base_url)
    assert "Status: ABANDONED" in details[0]["text"]


# TODO: Exercise MCP transport and expand E2E coverage to other tools and plugins.
