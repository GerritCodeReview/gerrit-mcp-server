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
CONFIG_FILE="gerrit_mcp_server/gerrit_config.json"
SAMPLE_CONFIG_FILE="gerrit_mcp_server/gerrit_config.sample.json"

# --- Config Bootstrap ---
# Create the config file from the sample if it doesn't exist
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}Configuration file not found. Creating from sample...${NC}"
    if ! cp "$SAMPLE_CONFIG_FILE" "$CONFIG_FILE"; then
        echo -e "${RED}Failed to create configuration file. Aborting tests.${NC}"
        exit 1
    fi
fi

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
export GERRIT_CONFIG_PATH="$(pwd)/tests/test_config.json"

# Run tests using pytest
echo -e "\n${YELLOW}Running tests with pytest...${NC}"
if ! python -m pytest; then
    echo -e "${RED}Tests failed.${NC}"
    exit 1
fi

echo -e "\n${GREEN}All tests passed successfully.${NC}"