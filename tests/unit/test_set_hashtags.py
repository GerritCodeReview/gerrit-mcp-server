import json
from unittest.mock import AsyncMock, patch

import pytest

from gerrit_mcp_server import main

GERRIT_BASE_URL = "https://my-gerrit.com"
HASHTAGS_URL = f"{GERRIT_BASE_URL}/changes/12345/hashtags"


@pytest.mark.asyncio
async def test_set_hashtags_posts_add_and_remove():
    with patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock) as mock:
        mock.return_value = json.dumps(["new-tag", "kept"])

        result = await main.set_hashtags(
            "12345",
            add=["new-tag"],
            remove=["old-tag"],
            gerrit_base_url=GERRIT_BASE_URL,
        )

        assert result == {"change_id": "12345", "hashtags": ["new-tag", "kept"]}
        payload = json.dumps({"add": ["new-tag"], "remove": ["old-tag"]})
        mock.assert_called_once_with(
            [
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "--data",
                payload,
                HASHTAGS_URL,
            ],
            GERRIT_BASE_URL,
        )


@pytest.mark.asyncio
async def test_set_hashtags_sends_only_given_side():
    with patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock) as mock:
        mock.return_value = json.dumps(["new-tag"])

        await main.set_hashtags(
            "12345", add=["new-tag"], gerrit_base_url=GERRIT_BASE_URL
        )

        args = mock.call_args.args[0]
        assert json.loads(args[args.index("--data") + 1]) == {"add": ["new-tag"]}


@pytest.mark.asyncio
async def test_set_hashtags_without_update_reads_hashtags():
    with patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock) as mock:
        mock.return_value = json.dumps(["kept"])

        result = await main.set_hashtags("12345", gerrit_base_url=GERRIT_BASE_URL)

        assert result["hashtags"] == ["kept"]
        mock.assert_called_once_with([HASHTAGS_URL], GERRIT_BASE_URL)


@pytest.mark.asyncio
async def test_set_hashtags_raises_with_gerrit_answer():
    with patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock) as mock:
        mock.return_value = "hashtag edit not permitted"

        with pytest.raises(ValueError, match="hashtag edit not permitted"):
            await main.set_hashtags(
                "12345", add=["new-tag"], gerrit_base_url=GERRIT_BASE_URL
            )
