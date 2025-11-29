#!/usr/bin/env python3
"""
Show all decisions with execution errors from the database.

This script helps you identify and debug failed trade executions.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.database import set_database_path, get_db_connection, init_database
import json


def show_errors(mode='live'):
    """Show all decisions with execution errors."""
    set_database_path(mode)
    init_database()

    print(f"\n{'='*70}")
    print(f"EXECUTION ERRORS - {mode.upper()} MODE")
    print(f"{'='*70}\n")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get all failed decisions
        cursor.execute("""
            SELECT
                id,
                timestamp,
                coin,
                signal,
                execution_status,
                execution_error,
                execution_timestamp,
                quantity_usd,
                leverage,
                confidence
            FROM decisions
            WHERE execution_status = 'failed' OR execution_error IS NOT NULL
            ORDER BY timestamp DESC
        """)

        errors = [dict(row) for row in cursor.fetchall()]

        if not errors:
            print("✓ No execution errors found!\n")
            return

        print(f"Found {len(errors)} decision(s) with execution errors:\n")

        for i, error in enumerate(errors, 1):
            print(f"[{i}] Decision #{error['id']} - {error['timestamp']}")
            print(f"    Coin: {error['coin']}")
            print(f"    Signal: {error['signal']}")
            print(f"    Size: ${error['quantity_usd']} @ {error['leverage']}x leverage")
            print(f"    Confidence: {error['confidence']*100:.0f}%")
            print(f"    Status: {error['execution_status']}")
            print(f"    Error: {error['execution_error']}")
            print(f"    Execution Time: {error['execution_timestamp']}")
            print()

        # Also check bot_status table for errors
        cursor.execute("""
            SELECT
                timestamp,
                status,
                message,
                error
            FROM bot_status
            WHERE status = 'error' OR error IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 10
        """)

        bot_errors = [dict(row) for row in cursor.fetchall()]

        if bot_errors:
            print(f"\n{'='*70}")
            print("RECENT BOT STATUS ERRORS")
            print(f"{'='*70}\n")

            for i, err in enumerate(bot_errors, 1):
                print(f"[{i}] {err['timestamp']}")
                print(f"    Status: {err['status']}")
                print(f"    Message: {err['message']}")
                if err['error']:
                    print(f"    Error: {err['error']}")
                print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Show execution errors')
    parser.add_argument(
        '--mode',
        choices=['live', 'paper', 'both'],
        default='live',
        help='Which database to check (default: live)'
    )

    args = parser.parse_args()

    if args.mode == 'both':
        show_errors('live')
        print()
        show_errors('paper')
    else:
        show_errors(args.mode)


if __name__ == "__main__":
    main()
