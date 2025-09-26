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

import unittest
from gerrit_mcp_server.sort_util import sort_changes_by_date


class TestSortUtil(unittest.TestCase):

    def test_sort_changes_by_date(self):
        changes = [
            {"updated": "2023-01-01T00:00:00.000000000Z"},
            {"updated": "2023-01-03T00:00:00.000000000Z"},
            {"updated": "2023-01-02T00:00:00.000000000Z"},
        ]
        sorted_changes = sort_changes_by_date(changes)
        self.assertEqual(sorted_changes[0]["updated"], "2023-01-03T00:00:00.000000000Z")
        self.assertEqual(sorted_changes[1]["updated"], "2023-01-02T00:00:00.000000000Z")
        self.assertEqual(sorted_changes[2]["updated"], "2023-01-01T00:00:00.000000000Z")

    def test_sort_changes_by_date_empty_list(self):
        self.assertEqual(sort_changes_by_date([]), [])

    def test_sort_changes_by_date_single_change(self):
        changes = [{"updated": "2023-01-01T00:00:00.000000000Z"}]
        self.assertEqual(sort_changes_by_date(changes), changes)


if __name__ == "__main__":
    unittest.main()
