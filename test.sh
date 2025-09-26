#!/bin/bash
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

# This script runs the unit and integration tests for the Gerrit MCP server.

# --- Color Codes ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Virtual Environment ---
VENV_DIR=".venv"

# Check if the virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual environment not found. Running the build script...${NC}"
    if ! ./build-gerrit.sh; then
        echo -e "${RED}Build script failed. Aborting tests.${NC}"
        exit 1
    fi
fi

# Activate the virtual environment
source "$VENV_DIR/bin/activate"

# --- Test Execution ---
# Set PYTHONPATH to include the project root
export PYTHONPATH=$(pwd)

# Run tests using the python from the virtual environment
# The original script had logic to differentiate between E2E and other tests.
# This version simplifies to run all tests discovered under 'tests/'.
# If E2E tests are needed, the script would need to be modified to handle the --e2e flag.
echo -e "\n${YELLOW}Running unit and integration tests...${NC}"
if ! python -m unittest discover tests; then
    echo -e "${RED}Tests failed.${NC}"
    exit 1
fi

echo -e "\n${GREEN}All tests passed successfully.${NC}"