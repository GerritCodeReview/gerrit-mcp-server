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

# This script builds the Gerrit MCP server by setting up its Python environment.

# --- Prepend common user binary paths to PATH for cross-platform compatibility ---
# This helps find tools like pipx and uv if they were installed by the user.
export PATH="$HOME/.local/bin:$HOME/Library/Python/3.9/bin:$PATH"

# --- Color Codes ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Build Logic ---
SERVER_DIR="."
REQUIREMENTS_FILE="requirements.txt"
VENV_DIR=".venv"

echo -e "\n${YELLOW}Setting up the Python environment for the Gerrit MCP server...${NC}"

# Create a build directory to indicate the server is "installed"
mkdir -p "build"

# Create a virtual environment
echo "Creating virtual environment in ${VENV_DIR}..."
if ! python3 -m venv "${VENV_DIR}"; then
    echo -e "${RED}Failed to create virtual environment.${NC}"
    exit 1
fi

# Activate the virtual environment for the rest of the script
source "${VENV_DIR}/bin/activate"

# Install uv into the virtual environment
echo "Installing uv..."
if ! pip3 install -r uv-requirements.txt --require-hashes; then
    echo -e "${RED}Failed to install uv.${NC}"
    exit 1
fi

# Use uv to compile dependencies into a requirements.txt file with hashes
echo "Compiling dependencies and generating hashes..."
if ! uv pip compile pyproject.toml --generate-hashes --output-file ${REQUIREMENTS_FILE} --extra dev --extra-index-url https://pypi.org/simple; then
    echo -e "\n${RED}Failed to compile dependencies.${NC}"
    exit 1
fi

# Use uv to install dependencies from the requirements.txt file
echo "Installing dependencies from ${REQUIREMENTS_FILE}..."
if ! uv pip sync ${REQUIREMENTS_FILE}; then
    echo -e "\n${RED}Failed to set up the Python environment.${NC}"
    exit 1
fi

# Use uv to install the gerrit_mcp_server package securely with hash verification
echo "Building and installing the gerrit_mcp_server package..."
if ! uv build; then
    echo -e "\n${RED}Failed to build the gerrit_mcp_server package.${NC}"
    exit 1
fi

WHEEL_FILE=$(ls dist/*.whl | head -n 1)
WHEEL_HASH=$(sha256sum "${WHEEL_FILE}" | awk '{print $1}')
echo "${WHEEL_FILE} --hash=sha256:${WHEEL_HASH}" > local-requirements.txt

if ! uv pip install -r local-requirements.txt --no-deps --require-hashes; then
    echo -e "\n${RED}Failed to install the gerrit_mcp_server package.${NC}"
    rm local-requirements.txt
    exit 1
fi

rm local-requirements.txt
# Optionally keep dist/ for debugging or remove it:
# rm -rf dist/


echo -e "\n${GREEN}Successfully set up the Gerrit MCP server environment.${NC}"