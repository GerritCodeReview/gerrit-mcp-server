#!/usr/bin/env bash
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
export PATH="$HOME/.local/bin:$HOME/Library/Python/3.9/bin:$PATH"

# --- Color Codes ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "\n${YELLOW}Setting up the Python environment for the Gerrit MCP server...${NC}"

# Use the host uv if available; otherwise install it via pip.
if ! command -v uv &>/dev/null; then
    echo "uv not found on PATH, installing via pip..."
    if ! pip3 install uv; then
        echo -e "${RED}Failed to install uv. Install it manually: https://docs.astral.sh/uv/getting-started/installation/${NC}"
        exit 1
    fi
fi

# Install all dependencies (including dev extras) into .venv and sync uv.lock.
# uv sync targets UV_PROJECT_ENVIRONMENT when set (so build and the hook/MCP
# server agree on the env path), falling back to ./.venv for standalone use.
echo "Installing dependencies into: ${UV_PROJECT_ENVIRONMENT:-./.venv}"
if ! uv sync --extra dev; then
    echo -e "${RED}Failed to install dependencies.${NC}"
    exit 1
fi

echo -e "\n${GREEN}Successfully set up the Gerrit MCP server environment.${NC}"
echo -e "Activate the virtual environment with: ${YELLOW}source .venv/bin/activate${NC}"
