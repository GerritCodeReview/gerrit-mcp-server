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
from typing import Set


def extract_bugs_from_commit_message(commit_message: str) -> Set[str]:
    """
    Extracts bug IDs from a commit message.

    This function supports various formats for bug IDs, including:
    - Bug: 12345
    - Fixes: b/12345
    - Closes: 12345, b/67890
    - Inline mentions like b/12345.
    """
    bug_ids = set()

    # Pattern for lines starting with Bug, Fixes, or Closes.
    # This captures the rest of the line.
    footer_pattern = r"^\s*(?:Bug|Fixes|Closes)\s*:\s*(.*)"
    footer_matches = re.findall(
        footer_pattern, commit_message, re.MULTILINE | re.IGNORECASE
    )

    for line in footer_matches:
        # Split the line by common separators like comma or space.
        potential_ids = re.split(r"[\s,]+", line)
        for pid in potential_ids:
            if not pid:
                continue
            # Match bug IDs that are optionally prefixed with 'b/'.
            bug_id_match = re.fullmatch(r"(?:b/)?(\d+)", pid)
            if bug_id_match:
                bug_ids.add(bug_id_match.group(1))

    # Pattern for inline bug mentions, e.g., "This fixes b/12345".
    inline_pattern = r"\bb/(\d+)\b"
    inline_matches = re.findall(inline_pattern, commit_message, re.IGNORECASE)
    for mid in inline_matches:
        bug_ids.add(mid)

    return bug_ids