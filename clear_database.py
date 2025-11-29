#!/usr/bin/env python3
"""
Clear all data from the trading database.

Use this to reset the database and start fresh.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from web.database import get_db_connection, init_database, set_database_path

def clear_all_data(mode='live'):
    """Delete all records from all tables."""
    set_database_path(mode)
    init_database()

    print(f"\nClearing {mode.upper()} trading database...")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Delete all data from tables
        cursor.execute("DELETE FROM decisions")
        decisions_deleted = cursor.rowcount

        cursor.execute("DELETE FROM account_state")
        accounts_deleted = cursor.rowcount

        cursor.execute("DELETE FROM positions")
        positions_deleted = cursor.rowcount

        cursor.execute("DELETE FROM bot_status")
        status_deleted = cursor.rowcount

        # Reset autoincrement counters
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('decisions', 'account_state', 'positions', 'bot_status')")

        conn.commit()

    print(f"  Deleted {decisions_deleted} decisions")
    print(f"  Deleted {accounts_deleted} account states")
    print(f"  Deleted {positions_deleted} positions")
    print(f"  Deleted {status_deleted} status logs")
    print()
    print(f"[OK] {mode.upper()} database cleared! Starting fresh.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Clear trading bot database')
    parser.add_argument('--mode', choices=['live', 'paper', 'both'], default='live',
                        help='Which database to clear (default: live)')

    args = parser.parse_args()

    confirm = input(f"Are you sure you want to clear {args.mode.upper()} database? (yes/no): ")

    if confirm.lower() == 'yes':
        if args.mode == 'both':
            clear_all_data('live')
            clear_all_data('paper')
        else:
            clear_all_data(args.mode)
    else:
        print("Cancelled.")
