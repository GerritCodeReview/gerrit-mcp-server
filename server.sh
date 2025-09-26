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

# server.sh: A script to manage the Gerrit MCP server.

# --- Configuration ---
# Get the directory where the script is located.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# The command to run your server.
# IMPORTANT: This should not include redirection (>) or backgrounding (&).
# The script handles that automatically.
SERVER_COMMAND=".venv/bin/uvicorn gerrit_mcp_server.main:app --host localhost --port 6322"

# The file to store the Process ID (PID) of the running server.
PID_FILE="$SCRIPT_DIR/server.pid"

# The file to store the server's logs.
LOG_FILE="$SCRIPT_DIR/server.log"

# --- Functions ---

# Function to check if the server is currently running.
# It checks for the PID file and then verifies if the process is active.
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        # Check if a process with this PID exists.
        # The >/dev/null 2>&1 suppresses output from the ps command.
        if ps -p $PID > /dev/null 2>&1; then
            return 0 # 0 means true (is running)
        fi
    fi
    return 1 # 1 means false (is not running)
}

# Function to start the server.
start_server() {
    if is_running; then
        echo "Server is already running with PID $(cat "$PID_FILE")."
        exit 1
    fi

    echo "Starting server..."
    # Use setsid to run the server in a new session, creating a new process group.
    # This prevents the stop command from killing the script that called it (e.g., the test runner).
    $SERVER_COMMAND > "$LOG_FILE" 2>&1 & disown

    # '$!' is a special variable that holds the PID of the last command run in the background.
    echo $! > "$PID_FILE"

    # Give it a moment to ensure it started correctly.
    sleep 1

    if is_running; then
        echo "Server started successfully with PID $(cat "$PID_FILE")."
        echo "Logs are being written to $LOG_FILE."
    else
        echo "Error: Server failed to start. Check '$LOG_FILE' for details."
        # Clean up the stale PID file if the server failed to start.
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Function to stop the server.
stop_server() {
    if ! is_running; then
        echo "Server is not running."
        if [ -f "$PID_FILE" ]; then
            echo "Cleaning up stale PID file: $PID_FILE"
            rm -f "$PID_FILE"
        fi
        exit 0
    fi

    PID=$(cat "$PID_FILE")
    PGID=$(ps -o pgid= -p "$PID" | grep -o '[0-9]*')

    echo "Stopping server process group with PGID $PGID..."

    # Kill the entire process group gracefully
    if kill -s SIGTERM -- -$PGID; then
        # Wait for the process group to actually terminate
        for i in {1..5}; do
            if ! ps -p $PID > /dev/null 2>&1; then
                echo "Server stopped successfully."
                rm -f "$PID_FILE"
                exit 0
            fi
            sleep 1
        done

        echo "Warning: Server did not stop gracefully. Forcing shutdown (kill -9)."
        kill -s SIGKILL -- -$PGID
        rm -f "$PID_FILE"
        echo "Server shutdown forced."
    else
        echo "Error: Failed to send stop signal to process group $PGID."
        exit 1
    fi
}

# Function to check the status of the server.
check_status() {
    if is_running; then
        echo "Server is RUNNING with PID $(cat "$PID_FILE")."
    else
        echo "Server is STOPPED."
    fi
}

# Function to tail the server logs.
tail_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "Log file not found: $LOG_FILE"
        echo "Has the server been started at least once?"
        exit 1
    fi
    echo "Tailing logs from $LOG_FILE... (Press Ctrl+C to stop)"
    # 'tail -f' follows the file, showing new lines as they are added.
    tail -f "$LOG_FILE"
}

# Function to restart the server.
restart_server() {
    echo "Restarting server..."
    # Stop the server; the stop command handles cases where it's already stopped.
    "$0" stop
    # Start the server again.
    "$0" start
}

# --- Main Script Logic ---

# Check the first command-line argument ($1) to decide what to do.
case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        check_status
        ;;
    logs)
        tail_logs
        ;;
    *)
        # If the argument is not recognized, show a usage message.
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac

exit 0