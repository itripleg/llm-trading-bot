#!/usr/bin/env python3
"""
Clear all data from the trading bot database.

This script will delete all entries from all tables but keep the schema intact.
Useful for starting fresh during testing.

DANGER: This will permanently delete all trading history!
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.database import set_database_path, get_db_connection, init_database


def clear_database(mode: str = "live"):
    """
    Clear all data from the database.

    Args:
        mode: 'live' or 'paper'
    """
    set_database_path(mode)

    # Make sure database exists
    init_database()

    print(f"\n{'='*70}")
    print(f"CLEARING {mode.upper()} DATABASE")
    print(f"{'='*70}\n")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row['name'] for row in cursor.fetchall()]

        print("Tables found:", ", ".join(tables))
        print()

        # Count entries before deletion
        print("Current entry counts:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cursor.fetchone()['count']
            print(f"  {table}: {count} entries")

        # Confirm deletion
        print(f"\n{'!'*70}")
        print("WARNING: This will permanently delete ALL data from the database!")
        print(f"{'!'*70}\n")

        response = input("Type 'DELETE' to confirm: ")

        if response != "DELETE":
            print("\n[CANCELLED] Database not cleared.")
            return False

        # Delete all data from each table
        print("\nDeleting data...")
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            deleted = cursor.rowcount
            print(f"  {table}: deleted {deleted} entries")

        # Reset auto-increment counters
        print("\nResetting ID counters...")
        for table in tables:
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")

        conn.commit()

        # Verify deletion
        print("\nVerifying deletion...")
        all_empty = True
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cursor.fetchone()['count']
            if count > 0:
                print(f"  {table}: WARNING - still has {count} entries!")
                all_empty = False
            else:
                print(f"  {table}: ✓ empty")

        if all_empty:
            print(f"\n{'='*70}")
            print(f"✓ {mode.upper()} DATABASE CLEARED SUCCESSFULLY")
            print(f"{'='*70}\n")
            return True
        else:
            print(f"\n{'='*70}")
            print("✗ DATABASE CLEARING FAILED - SOME DATA REMAINS")
            print(f"{'='*70}\n")
            return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Clear trading bot database")
    parser.add_argument(
        "--mode",
        choices=["live", "paper", "both"],
        default="live",
        help="Which database to clear (default: live)"
    )

    args = parser.parse_args()

    if args.mode == "both":
        print("\nClearing BOTH live and paper databases...\n")
        clear_database("live")
        print("\n")
        clear_database("paper")
    else:
        clear_database(args.mode)


if __name__ == "__main__":
    main()
