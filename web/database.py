"""
Database layer for storing trading bot data using SQLite.

Tables:
- decisions: All Claude trading decisions
- account_state: Balance, PnL, Sharpe ratio snapshots
- positions: Position history (entry/exit)
- bot_status: Bot activity logs
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# Database file location (default)
DB_PATH = Path(__file__).parent.parent / "data" / "trading_bot.db"


def set_database_path(mode: str = "paper"):
    """
    Set the database path based on trading mode.

    Args:
        mode: 'paper' or 'live'
    """
    global DB_PATH
    base_dir = Path(__file__).parent.parent / "data"

    if mode == "live":
        DB_PATH = base_dir / "trading_bot_live.db"
    else:
        DB_PATH = base_dir / "trading_bot_paper.db"


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """
    Initialize the database schema.
    Creates all tables if they don't exist.
    """
    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Decisions table - stores all Claude trading decisions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                coin TEXT NOT NULL,
                signal TEXT NOT NULL,
                quantity_usd REAL NOT NULL,
                leverage REAL NOT NULL,
                confidence REAL NOT NULL,
                profit_target REAL,
                stop_loss REAL,
                invalidation_condition TEXT,
                justification TEXT NOT NULL,
                raw_response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Account state table - snapshots of account over time
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                balance_usd REAL NOT NULL,
                equity_usd REAL NOT NULL,
                unrealized_pnl REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                sharpe_ratio REAL,
                num_positions INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Positions table - track all position entries and exits
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id TEXT UNIQUE NOT NULL,
                coin TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity_usd REAL NOT NULL,
                leverage REAL NOT NULL,
                decision_id INTEGER,
                exit_time TEXT,
                exit_price REAL,
                realized_pnl REAL,
                status TEXT DEFAULT 'open',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (decision_id) REFERENCES decisions(id)
            )
        """)

        # Migrate existing positions table to add decision_id if missing
        try:
            cursor.execute("SELECT decision_id FROM positions LIMIT 1")
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            cursor.execute("ALTER TABLE positions ADD COLUMN decision_id INTEGER")
            print("[DB Migration] Added decision_id column to positions table")

        # Migrate decisions table to add prompt storage columns
        try:
            cursor.execute("SELECT system_prompt FROM decisions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE decisions ADD COLUMN system_prompt TEXT")
            cursor.execute("ALTER TABLE decisions ADD COLUMN user_prompt TEXT")
            print("[DB Migration] Added prompt columns to decisions table")

        # Migrate decisions table to add execution tracking columns
        try:
            cursor.execute("SELECT execution_status FROM decisions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE decisions ADD COLUMN execution_status TEXT DEFAULT 'pending'")
            cursor.execute("ALTER TABLE decisions ADD COLUMN execution_error TEXT")
            cursor.execute("ALTER TABLE decisions ADD COLUMN execution_timestamp TEXT")
            print("[DB Migration] Added execution tracking columns to decisions table")

        # Migrate user_inputs table to add message_type and image_path columns
        try:
            cursor.execute("SELECT message_type FROM user_inputs LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE user_inputs ADD COLUMN message_type TEXT DEFAULT 'cycle'")
            cursor.execute("ALTER TABLE user_inputs ADD COLUMN image_path TEXT")
            print("[DB Migration] Added message_type and image_path columns to user_inputs table")

        # Bot status table - activity logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # User inputs table - store user guidance/comments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_inputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                message TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Bot settings table - store configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize default settings if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO bot_settings (key, value)
            VALUES
                ('prompt_preset', 'aggressive_small_account'),
                ('min_margin_usd', '1.0'),
                ('min_balance_threshold', '1.0'),
                ('max_margin_usd', '1000.0'),
                ('execution_interval_seconds', '600'),
                ('max_open_positions', '3')
        """)

        # Create indices for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_decisions_timestamp
            ON decisions(timestamp DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_account_timestamp
            ON account_state(timestamp DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_status
            ON positions(status)
        """)

        print(f"[OK] Database initialized at {DB_PATH}")


# ============================================================================
# DECISION OPERATIONS
# ============================================================================

def save_decision(
    decision_data: Dict[str, Any],
    raw_response: Optional[str] = None,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None
) -> int:
    """
    Save a Claude trading decision to the database.

    Args:
        decision_data: Dictionary with keys matching TradeDecision model
        raw_response: Optional raw JSON response from Claude
        system_prompt: Optional system prompt sent to Claude
        user_prompt: Optional user prompt sent to Claude

    Returns:
        The ID of the inserted decision
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        timestamp = datetime.utcnow().isoformat()
        exit_plan = decision_data.get('exit_plan', {}) or {}

        cursor.execute("""
            INSERT INTO decisions (
                timestamp, coin, signal, quantity_usd, leverage, confidence,
                profit_target, stop_loss, invalidation_condition, justification, raw_response,
                system_prompt, user_prompt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            decision_data['coin'],
            decision_data['signal'],
            decision_data['quantity_usd'],
            decision_data['leverage'],
            decision_data['confidence'],
            exit_plan.get('profit_target'),
            exit_plan.get('stop_loss'),
            exit_plan.get('invalidation_condition'),
            decision_data['justification'],
            raw_response,
            system_prompt,
            user_prompt
        ))

        return cursor.lastrowid


def get_recent_decisions(limit: int = 20) -> List[Dict[str, Any]]:
    """Get the most recent trading decisions with position data if available."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                d.*,
                p.entry_price,
                p.exit_price,
                p.realized_pnl
            FROM decisions d
            LEFT JOIN positions p ON (
                -- For entry signals, match on decision_id
                (d.signal IN ('buy_to_enter', 'sell_to_enter') AND d.id = p.decision_id)
                OR
                -- For hold/close signals, find the most recent position for that coin
                (d.signal IN ('hold', 'close') AND d.coin = p.coin
                 AND p.entry_time = (
                     SELECT MAX(p2.entry_time)
                     FROM positions p2
                     WHERE p2.coin = d.coin
                     AND p2.entry_time <= d.timestamp
                 ))
            )
            ORDER BY d.timestamp DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]


def get_decisions_by_coin(coin: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent decisions for a specific coin."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM decisions
            WHERE coin = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (coin, limit))

        return [dict(row) for row in cursor.fetchall()]


def update_decision_execution(
    decision_id: int,
    status: str,
    error: Optional[str] = None
) -> bool:
    """
    Update a decision's execution status.

    Args:
        decision_id: ID of the decision to update
        status: Execution status ('success', 'failed', 'skipped', 'pending')
        error: Optional error message if execution failed

    Returns:
        True if updated successfully
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        timestamp = datetime.utcnow().isoformat()

        cursor.execute("""
            UPDATE decisions
            SET execution_status = ?,
                execution_error = ?,
                execution_timestamp = ?
            WHERE id = ?
        """, (status, error, timestamp, decision_id))

        return cursor.rowcount > 0


# ============================================================================
# ACCOUNT STATE OPERATIONS
# ============================================================================

def save_account_state(
    balance_usd: float,
    equity_usd: float,
    unrealized_pnl: float = 0,
    realized_pnl: float = 0,
    sharpe_ratio: Optional[float] = None,
    num_positions: int = 0
) -> int:
    """Save a snapshot of account state."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        timestamp = datetime.utcnow().isoformat()
        total_pnl = realized_pnl + unrealized_pnl

        cursor.execute("""
            INSERT INTO account_state (
                timestamp, balance_usd, equity_usd, unrealized_pnl,
                realized_pnl, total_pnl, sharpe_ratio, num_positions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, balance_usd, equity_usd, unrealized_pnl,
            realized_pnl, total_pnl, sharpe_ratio, num_positions
        ))

        return cursor.lastrowid


def get_latest_account_state() -> Optional[Dict[str, Any]]:
    """Get the most recent account state snapshot."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM account_state
            ORDER BY timestamp DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        return dict(row) if row else None


def get_account_history(limit: int = 100) -> List[Dict[str, Any]]:
    """Get account state history for charting."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM account_state
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]


# ============================================================================
# POSITION OPERATIONS
# ============================================================================

def save_position_entry(
    position_id: str,
    coin: str,
    side: str,
    entry_price: float,
    quantity_usd: float,
    leverage: float,
    decision_id: Optional[int] = None
) -> int:
    """Record a new position entry."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        entry_time = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO positions (
                position_id, coin, side, entry_time, entry_price,
                quantity_usd, leverage, decision_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
        """, (position_id, coin, side, entry_time, entry_price, quantity_usd, leverage, decision_id))

        return cursor.lastrowid


def close_position(position_id: str, exit_price: float, realized_pnl: float) -> bool:
    """Mark a position as closed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        exit_time = datetime.utcnow().isoformat()

        cursor.execute("""
            UPDATE positions
            SET exit_time = ?, exit_price = ?, realized_pnl = ?, status = 'closed'
            WHERE position_id = ?
        """, (exit_time, exit_price, realized_pnl, position_id))

        return cursor.rowcount > 0


def get_open_positions() -> List[Dict[str, Any]]:
    """Get all currently open positions with their original exit plans."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.*,
                d.profit_target,
                d.stop_loss,
                d.invalidation_condition,
                d.justification as entry_justification
            FROM positions p
            LEFT JOIN decisions d ON p.decision_id = d.id
            WHERE p.status = 'open'
            ORDER BY p.entry_time DESC
        """)

        return [dict(row) for row in cursor.fetchall()]


def get_closed_positions(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recently closed positions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM positions
            WHERE status = 'closed'
            ORDER BY exit_time DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]


def get_all_positions(limit: int = 100) -> List[Dict[str, Any]]:
    """Get all positions (open and closed)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM positions
            ORDER BY entry_time DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]


def get_total_realized_pnl() -> float:
    """Calculate total realized PnL from all closed positions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SUM(realized_pnl) as total
            FROM positions
            WHERE status = 'closed' AND realized_pnl IS NOT NULL
        """)

        result = cursor.fetchone()
        return float(result['total']) if result and result['total'] is not None else 0.0


# ============================================================================
# BOT STATUS OPERATIONS
# ============================================================================

def log_bot_status(status: str, message: Optional[str] = None, error: Optional[str] = None):
    """Log bot activity status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        timestamp = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO bot_status (timestamp, status, message, error)
            VALUES (?, ?, ?, ?)
        """, (timestamp, status, message, error))


def get_latest_bot_status() -> Optional[Dict[str, Any]]:
    """Get the most recent bot status log."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM bot_status
            ORDER BY timestamp DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        return dict(row) if row else None


def get_bot_status_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent bot status logs."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM bot_status
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]


# ============================================================================
# USER INPUT OPERATIONS
# ============================================================================

def save_user_input(message: str, message_type: str = 'cycle', image_path: Optional[str] = None) -> int:
    """
    Save a new user input message.
    Automatically archives previous active messages (sets is_active=0).

    Args:
        message: The user's text message
        message_type: 'cycle' (included in next cycle) or 'interrupt' (trigger immediate decision)
        image_path: Optional path to uploaded image (for chart analysis)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.utcnow().isoformat()

        # Archive previous active messages
        cursor.execute("UPDATE user_inputs SET is_active = 0 WHERE is_active = 1")

        # Insert new message
        cursor.execute("""
            INSERT INTO user_inputs (timestamp, message, message_type, image_path, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (timestamp, message, message_type, image_path))

        return cursor.lastrowid


def get_active_user_input() -> Optional[Dict[str, Any]]:
    """Get the currently active user input message."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM user_inputs
            WHERE is_active = 1
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


def archive_user_input(input_id: int) -> bool:
    """Archive a specific user input (mark as inactive)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE user_inputs SET is_active = 0 WHERE id = ?", (input_id,))
        return cursor.rowcount > 0


# ============================================================================
# BOT SETTINGS
# ============================================================================

def get_bot_setting(key: str, default: str = None) -> Optional[str]:
    """
    Get a bot setting value.

    Args:
        key: Setting key
        default: Default value if not found

    Returns:
        Setting value or default
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default


def set_bot_setting(key: str, value: str) -> bool:
    """
    Set a bot setting value.

    Args:
        key: Setting key
        value: Setting value

    Returns:
        True if successful
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO bot_settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, timestamp))
        return cursor.rowcount > 0


def get_active_prompt_preset() -> str:
    """Get the currently active prompt preset name."""
    return get_bot_setting('prompt_preset', 'aggressive_small_account')


def set_active_prompt_preset(preset_name: str) -> bool:
    """Set the active prompt preset."""
    return set_bot_setting('prompt_preset', preset_name)


def get_bot_config() -> Dict[str, Any]:
    """Get all bot configuration settings."""
    return {
        'min_margin_usd': float(get_bot_setting('min_margin_usd', '1.0')),
        'min_balance_threshold': float(get_bot_setting('min_balance_threshold', '1.0')),
        'max_margin_usd': float(get_bot_setting('max_margin_usd', '1000.0')),
        'execution_interval_seconds': int(get_bot_setting('execution_interval_seconds', '600')),
        'max_open_positions': int(get_bot_setting('max_open_positions', '3')),
    }


def update_bot_config(config: Dict[str, Any]) -> bool:
    """Update bot configuration settings."""
    try:
        for key, value in config.items():
            set_bot_setting(key, str(value))
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update bot config: {e}")
        return False


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("Initializing database...")
    init_database()

    # Test saving a decision
    print("\nTesting decision save...")
    decision = {
        'coin': 'BTC/USDC:USDC',
        'signal': 'buy_to_enter',
        'quantity_usd': 50.0,
        'leverage': 2.0,
        'confidence': 0.75,
        'exit_plan': {
            'profit_target': 111000.0,
            'stop_loss': 106361.0,
            'invalidation_condition': '4H RSI breaks below 40'
        },
        'justification': 'Strong bullish momentum with RSI confirmation'
    }
    decision_id = save_decision(decision)
    print(f"[OK] Saved decision with ID: {decision_id}")

    # Test saving account state
    print("\nTesting account state save...")
    account_id = save_account_state(
        balance_usd=1000.0,
        equity_usd=1050.0,
        unrealized_pnl=50.0,
        realized_pnl=0.0,
        sharpe_ratio=1.5,
        num_positions=1
    )
    print(f"[OK] Saved account state with ID: {account_id}")

    # Test saving position
    print("\nTesting position save...")
    pos_id = save_position_entry(
        position_id="BTC_20250113_001",
        coin="BTC/USDC:USDC",
        side="long",
        entry_price=99798.0,
        quantity_usd=50.0,
        leverage=2.0
    )
    print(f"[OK] Saved position with ID: {pos_id}")

    # Test bot status log
    print("\nTesting bot status log...")
    log_bot_status("running", "Bot started successfully")
    print("[OK] Logged bot status")

    # Retrieve and display recent data
    print("\n" + "="*60)
    print("Recent decisions:")
    decisions = get_recent_decisions(limit=5)
    for d in decisions:
        print(f"  {d['timestamp']} | {d['coin']} | {d['signal']} | ${d['quantity_usd']}")

    print("\nLatest account state:")
    account = get_latest_account_state()
    if account:
        print(f"  Balance: ${account['balance_usd']:.2f}")
        print(f"  Equity: ${account['equity_usd']:.2f}")
        print(f"  Total PnL: ${account['total_pnl']:.2f}")

    print("\nOpen positions:")
    positions = get_open_positions()
    for p in positions:
        print(f"  {p['position_id']} | {p['coin']} | {p['side']} | Entry: ${p['entry_price']}")

    print("\n[OK] All database tests passed!")


# ============================================================================
# DATABASE MANAGEMENT UTILITIES
# ============================================================================

def get_database_status() -> Dict[str, Any]:
    """
    Get current database statistics and status.
    
    Returns:
        Dictionary with database stats including table counts and file size
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get counts from each table
        cursor.execute("SELECT COUNT(*) FROM decisions")
        decisions_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM account_state")
        account_state_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM positions")
        positions_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM positions WHERE status = 'open'")
        open_positions_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM bot_status")
        bot_status_count = cursor.fetchone()[0]
        
        # Get latest timestamps
        cursor.execute("SELECT timestamp FROM decisions ORDER BY id DESC LIMIT 1")
        latest_decision = cursor.fetchone()
        latest_decision_time = latest_decision[0] if latest_decision else None
        
        cursor.execute("SELECT timestamp FROM account_state ORDER BY id DESC LIMIT 1")
        latest_account = cursor.fetchone()
        latest_account_time = latest_account[0] if latest_account else None
    
    # Get database file size
    db_size_bytes = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    db_size_mb = db_size_bytes / (1024 * 1024)
    
    return {
        'database_path': str(DB_PATH),
        'database_size_mb': round(db_size_mb, 2),
        'database_size_bytes': db_size_bytes,
        'table_counts': {
            'decisions': decisions_count,
            'account_state': account_state_count,
            'positions': positions_count,
            'open_positions': open_positions_count,
            'bot_status': bot_status_count
        },
        'latest_timestamps': {
            'decision': latest_decision_time,
            'account_state': latest_account_time
        },
        'last_updated': datetime.utcnow().isoformat()
    }


def reset_database(preserve_schema: bool = True) -> bool:
    """
    Reset the database by deleting all data.
    
    Args:
        preserve_schema: If True, keep tables and just delete data
                        If False, drop all tables and reinitialize
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if preserve_schema:
                # Just delete all data, keep schema
                cursor.execute("DELETE FROM decisions")
                cursor.execute("DELETE FROM account_state")
                cursor.execute("DELETE FROM positions")
                cursor.execute("DELETE FROM positions")
                cursor.execute("DELETE FROM bot_status")
                cursor.execute("DELETE FROM user_inputs")
                
                # Reset autoincrement counters
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='decisions'")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='account_state'")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='positions'")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='positions'")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='bot_status'")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='user_inputs'")

                # Reclaim disk space by running VACUUM
                cursor.execute("VACUUM")

                print(f"[OK] Database data cleared and disk space reclaimed: {DB_PATH}")
            else:
                # Drop all tables and reinitialize
                cursor.execute("DROP TABLE IF EXISTS decisions")
                cursor.execute("DROP TABLE IF EXISTS account_state")
                cursor.execute("DROP TABLE IF EXISTS positions")
                cursor.execute("DROP TABLE IF EXISTS positions")
                cursor.execute("DROP TABLE IF EXISTS bot_status")
                cursor.execute("DROP TABLE IF EXISTS user_inputs")
                cursor.execute("DROP TABLE IF EXISTS sqlite_sequence")
                
                print(f"[OK] Database tables dropped: {DB_PATH}")
                
        # Reinitialize schema if we dropped tables
        if not preserve_schema:
            init_database()
            print(f"[OK] Database schema reinitialized")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to reset database: {e}")
        import traceback
        traceback.print_exc()
        return False
