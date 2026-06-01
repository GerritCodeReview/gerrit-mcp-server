import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from gerrit_mcp_server import main


def _make_related_entry(
    change_number,
    change_id,
    project,
    subject,
    commit_sha,
    parents,
    status,
    revision_number,
    current_revision_number,
):
    return {
        "_change_number": change_number,
        "change_id": change_id,
        "project": project,
        "commit": {
            "commit": commit_sha,
            "subject": subject,
            "parents": [{"commit": p} for p in parents],
        },
        "status": status,
        "_revision_number": revision_number,
        "_current_revision_number": current_revision_number,
    }


GERRIT_BASE_URL = "https://gerrit.example.com"

ENTRY_BASE = _make_related_entry(
    change_number=6871420,
    change_id="Iabc123base",
    project="coreplatform/wasp/core.wasp",
    subject="base: refactor shell init",
    commit_sha="9f3cabc",
    parents=["1a2bdef"],
    status="MERGED",
    revision_number=3,
    current_revision_number=3,
)

ENTRY_QUERIED = _make_related_entry(
    change_number=6871423,
    change_id="Iabc123queried",
    project="coreplatform/wasp/core.wasp",
    subject="feature: add new thing",
    commit_sha="deadbeef",
    parents=["9f3cabc"],
    status="NEW",
    revision_number=2,
    current_revision_number=2,
)

ENTRY_DESCENDANT = _make_related_entry(
    change_number=6871425,
    change_id="Iabc123desc",
    project="coreplatform/wasp/core.wasp",
    subject="followup: cleanup",
    commit_sha="cafebabe",
    parents=["deadbeef"],
    status="NEW",
    revision_number=1,
    current_revision_number=1,
)


class TestGetRelatedChanges(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_returns_mapped_fields(self, mock_run_curl):
        async def run_test():
            mock_response = {"changes": [ENTRY_DESCENDANT, ENTRY_QUERIED, ENTRY_BASE]}
            mock_run_curl.return_value = json.dumps(mock_response)

            result = await main.get_related_changes(
                "6871423", gerrit_base_url=GERRIT_BASE_URL
            )

            data = result
            self.assertEqual(data["change_id"], "6871423")
            self.assertEqual(data["revision_id"], "current")
            related = data["related_changes"]
            self.assertEqual(len(related), 3)

            # Ordering preserved: descendant first, queried second, base last
            self.assertEqual(related[0]["change_number"], 6871425)
            self.assertEqual(related[0]["commit_sha"], "cafebabe")
            self.assertEqual(related[0]["parents"], ["deadbeef"])
            self.assertEqual(related[0]["status"], "NEW")
            self.assertEqual(related[0]["subject"], "followup: cleanup")
            self.assertEqual(related[0]["project"], "coreplatform/wasp/core.wasp")
            self.assertEqual(related[0]["revision_number"], 1)
            self.assertEqual(related[0]["current_revision_number"], 1)

            self.assertEqual(related[1]["change_number"], 6871423)
            self.assertEqual(related[2]["change_number"], 6871420)
            self.assertEqual(related[2]["status"], "MERGED")

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_custom_revision_id(self, mock_run_curl):
        async def run_test():
            mock_response = {"changes": [ENTRY_QUERIED]}
            mock_run_curl.return_value = json.dumps(mock_response)

            result = await main.get_related_changes(
                "6871423",
                revision_id="abc123sha",
                gerrit_base_url=GERRIT_BASE_URL,
            )

            data = result
            self.assertEqual(data["revision_id"], "abc123sha")
            # Verify the URL used the custom revision_id
            call_args = mock_run_curl.call_args[0][0]
            self.assertIn("abc123sha", call_args[0])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_empty_changes_returns_note(self, mock_run_curl):
        async def run_test():
            mock_response = {"changes": []}
            mock_run_curl.return_value = json.dumps(mock_response)

            result = await main.get_related_changes(
                "6871423", gerrit_base_url=GERRIT_BASE_URL
            )

            data = result
            self.assertEqual(data["related_changes"], [])
            self.assertIn("note", data)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_stale_parent_fields_preserved(self, mock_run_curl):
        async def run_test():
            stale_entry = _make_related_entry(
                change_number=6871420,
                change_id="Istale",
                project="myproject",
                subject="stale parent",
                commit_sha="stalesha",
                parents=["rootsha"],
                status="NEW",
                revision_number=1,
                current_revision_number=3,
            )
            mock_response = {"changes": [ENTRY_QUERIED, stale_entry]}
            mock_run_curl.return_value = json.dumps(mock_response)

            result = await main.get_related_changes(
                "6871423", gerrit_base_url=GERRIT_BASE_URL
            )

            data = result
            base = data["related_changes"][1]
            self.assertEqual(base["revision_number"], 1)
            self.assertEqual(base["current_revision_number"], 3)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_json_decode_error(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "not valid json"

            with self.assertRaises(ValueError) as ctx:
                await main.get_related_changes(
                    "6871423", gerrit_base_url=GERRIT_BASE_URL
                )

            self.assertIn("Failed to parse", str(ctx.exception))

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_curl_exception(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception("404 Not Found")

            with self.assertRaises(Exception) as ctx:
                await main.get_related_changes(
                    "6871423", gerrit_base_url=GERRIT_BASE_URL
                )

            self.assertIn("6871423", str(ctx.exception))
            self.assertIn("404 Not Found", str(ctx.exception))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
