import unittest
from unittest.mock import patch, MagicMock
import asyncio

from gerrit_mcp_server.main import post_review_comment

class TestPostReviewComment(unittest.TestCase):
    @patch('gerrit_mcp_server.main.run_curl')
    def test_post_review_comment_with_labels(self, mock_run_curl):
        mock_run_curl.return_value = (0, '{"done": true}', '')
        asyncio.run(post_review_comment('123', 'test.py', 1, 'test comment', labels={'Verified': 1}, gerrit_base_url='https://gerrit-review.googlesource.com'))
        expected_payload_str = '{"comments": {"test.py": [{"line": 1, "message": "test comment", "unresolved": true}]}, "labels": {"Verified": 1}}'
        mock_run_curl.assert_called_with(
            [
                '-X',
                'POST',
                '-H',
                'Content-Type: application/json',
                '--data',
                expected_payload_str,
                'https://gerrit-review.googlesource.com/changes/123/revisions/current/review'
            ],
            'https://gerrit-review.googlesource.com'
        )

if __name__ == '__main__':
    unittest.main()
