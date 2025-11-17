#!/usr/bin/env python3
"""
Startup script for Alpha Arena Mini bot.

Starts the web server first, waits for it to be ready,
then starts the analysis bot.

Usage:
    python start_bot.py
"""

import sys
import os
import time
import signal
import subprocess
import requests
from pathlib import Path

# Configuration
WEB_SERVER_HOST = "localhost"
WEB_SERVER_PORT = 5000
WEB_SERVER_URL = f"http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}"
MAX_WAIT_TIME = 30  # seconds

# Process handles
web_process = None
bot_process = None


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\n[!] Shutting down...")

    if bot_process:
        print("[*] Stopping bot...")
        bot_process.terminate()
        try:
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bot_process.kill()

    if web_process:
        print("[*] Stopping web server...")
        web_process.terminate()
        try:
            web_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            web_process.kill()

    print("[*] Shutdown complete")
    sys.exit(0)


def wait_for_web_server(max_wait=MAX_WAIT_TIME):
    """
    Wait for web server to be ready by polling the health endpoint.

    Returns:
        bool: True if server is ready, False if timeout
    """
    print(f"\n[*] Waiting for web server at {WEB_SERVER_URL}...")

    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(WEB_SERVER_URL, timeout=2)
            if response.status_code == 200:
                print(f"[OK] Web server is ready!")
                return True
        except (requests.ConnectionError, requests.Timeout):
            # Server not ready yet
            pass

        time.sleep(1)

    print(f"[FAIL] Web server did not become ready within {max_wait} seconds")
    return False


def main():
    """Main startup routine."""
    global web_process, bot_process

    print("=" * 70)
    print("ALPHA ARENA MINI - STARTUP")
    print("=" * 70)
    print()

    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    # Get paths
    project_root = Path(__file__).parent
    web_script = project_root / "web" / "app.py"
    bot_script = project_root / "run_analysis_bot.py"
    python_exe = sys.executable

    # Verify scripts exist
    if not web_script.exists():
        print(f"[ERROR] Web server script not found: {web_script}")
        sys.exit(1)

    if not bot_script.exists():
        print(f"[ERROR] Bot script not found: {bot_script}")
        sys.exit(1)

    # Step 1: Start web server
    print("[1/3] Starting web server...")
    print(f"      Command: {python_exe} {web_script}")
    print()

    try:
        if sys.platform == 'win32':
            # Windows: Start in new console window
            web_process = subprocess.Popen(
                [python_exe, str(web_script)],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # Unix: Start in background
            web_process = subprocess.Popen(
                [python_exe, str(web_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

        print(f"[OK] Web server process started (PID: {web_process.pid})")
    except Exception as e:
        print(f"[ERROR] Failed to start web server: {e}")
        sys.exit(1)

    # Step 2: Wait for web server to be ready
    print("\n[2/3] Waiting for web server to be ready...")

    if not wait_for_web_server():
        print("[ERROR] Web server failed to start")
        if web_process:
            web_process.terminate()
        sys.exit(1)

    print(f"      Dashboard: {WEB_SERVER_URL}")

    # Step 3: Start analysis bot
    print("\n[3/3] Starting analysis bot...")
    print(f"      Command: {python_exe} {bot_script}")
    print()

    try:
        if sys.platform == 'win32':
            # Windows: Start in new console window AND save logs to files
            bot_log_dir = project_root / "logs"
            bot_log_dir.mkdir(exist_ok=True)
            bot_stdout_log = bot_log_dir / "bot_stdout.log"
            bot_stderr_log = bot_log_dir / "bot_stderr.log"

            bot_stdout = open(bot_stdout_log, 'w')
            bot_stderr = open(bot_stderr_log, 'w')

            # Set environment variable to prevent output buffering
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'

            # Start bot with redirected output to log files
            # Output will be visible in the new console window AND saved to logs
            bot_process = subprocess.Popen(
                [python_exe, str(bot_script)],
                env=env,
                stdout=bot_stdout,
                stderr=bot_stderr,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )

            print(f"[OK] Bot process started (PID: {bot_process.pid})")
            print(f"      Output: Visible in bot console window")
            print(f"      Logs: {bot_stdout_log}")
            print(f"            {bot_stderr_log}")
        else:
            # Unix: Start in background with log files
            bot_log_dir = project_root / "logs"
            bot_log_dir.mkdir(exist_ok=True)
            bot_stdout_log = bot_log_dir / "bot_stdout.log"
            bot_stderr_log = bot_log_dir / "bot_stderr.log"

            bot_stdout = open(bot_stdout_log, 'w')
            bot_stderr = open(bot_stderr_log, 'w')

            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'

            bot_process = subprocess.Popen(
                [python_exe, str(bot_script)],
                env=env,
                stdout=bot_stdout,
                stderr=bot_stderr
            )

            print(f"[OK] Bot process started (PID: {bot_process.pid})")
            print(f"      Logs: {bot_stdout_log}")
            print(f"            {bot_stderr_log}")

    except Exception as e:
        print(f"[ERROR] Failed to start bot: {e}")
        # Clean up web server
        if web_process:
            web_process.terminate()
        sys.exit(1)

    # All started successfully
    print("\n" + "=" * 70)
    print("ALL SYSTEMS RUNNING")
    print("=" * 70)
    print(f"\nWeb Dashboard: {WEB_SERVER_URL}")
    print(f"Web Server PID: {web_process.pid}")
    print(f"Bot PID: {bot_process.pid}")
    print("\nPress Ctrl+C to stop both processes")
    print("=" * 70)

    # Wait a few seconds and check if bot is still alive
    time.sleep(3)
    if bot_process.poll() is not None:
        print("\n[ERROR] Bot process died immediately after starting!")
        print("\nCheck the bot console window for errors.")

        # Clean up and exit
        if web_process:
            web_process.terminate()
        sys.exit(1)

    print("\n[OK] Bot is running successfully!")
    print("\nNote: Bot output is visible in the bot's console window.")
    print("      Close this window or press Ctrl+C to stop all processes.")

    # Keep script running and monitor processes
    try:
        while True:
            # Check if processes are still running
            web_alive = web_process.poll() is None
            bot_alive = bot_process.poll() is None

            if not web_alive:
                print("\n[WARNING] Web server process died!")
                if bot_process:
                    bot_process.terminate()
                break

            if not bot_alive:
                print("\n[WARNING] Bot process died!")
                print("Check the bot console window for errors.")
                # Don't kill web server - it might be useful for viewing history

            time.sleep(5)

    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()
