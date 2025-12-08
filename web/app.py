"""
Flask web server for trading bot dashboard.

Provides a simple web interface to monitor:
- Current account balance and PnL
- Active and closed positions
- Recent Claude trading decisions
- Bot status and activity logs
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from pathlib import Path
import sys
import subprocess
import psutil
import os

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.database import (
    init_database,
    get_recent_decisions,
    get_decisions_by_coin,
    get_latest_account_state,
    get_account_history,
    get_open_positions,
    get_closed_positions,
    get_all_positions,
    get_latest_bot_status,
    get_bot_status_history,
    set_database_path,
    get_db_connection,
    get_database_status,
    reset_database,
    save_user_input,
    get_active_user_input,
    archive_user_input
)
from config.settings import settings

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for potential API usage

# Set database path based on trading mode
db_mode = "live" if settings.is_live_trading() else "paper"
set_database_path(db_mode)
print(f"[DASHBOARD] Using database: trading_bot_{db_mode}.db")

# Initialize database on startup
init_database()


# ============================================================================
# HTML ROUTES
# ============================================================================

@app.route('/')
def dashboard():
    """Main dashboard page."""
    return render_template('dashboard.html')


# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/account')
def api_account():
    """
    Get current account state.

    For LIVE mode: Queries Hyperliquid API directly for real-time data
    For PAPER mode: Uses latest database snapshot

    Returns:
        JSON with balance, equity, PnL, positions count
    """
    # If live trading, get real-time data from Hyperliquid
    if settings.is_live_trading():
        try:
            from trading.executor import HyperliquidExecutor
            executor = HyperliquidExecutor(testnet=settings.hyperliquid_testnet)
            live_state = executor.get_account_state()

            if live_state:
                # Get realized PnL from database (Hyperliquid doesn't track this)
                db_account = get_latest_account_state()
                realized_pnl = db_account.get('realized_pnl', 0.0) if db_account else 0.0

                return jsonify({
                    'balance_usd': live_state.get('account_value', 0.0),
                    'equity_usd': live_state.get('account_value', 0.0),
                    'unrealized_pnl': live_state.get('unrealized_pnl', 0.0),
                    'realized_pnl': realized_pnl,
                    'total_pnl': live_state.get('unrealized_pnl', 0.0) + realized_pnl,
                    'num_positions': len(live_state.get('positions', [])),
                    'timestamp': live_state.get('timestamp'),
                    'source': 'hyperliquid_live'
                })
        except Exception as e:
            print(f"[ERROR] Failed to fetch live Hyperliquid data: {e}")
            # Fall back to database

    # Paper mode or live mode fallback: use database
    account = get_latest_account_state()

    if not account:
        # Return default state if no data
        return jsonify({
            'balance_usd': 0.0,
            'equity_usd': 0.0,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'total_pnl': 0.0,
            'sharpe_ratio': None,
            'num_positions': 0,
            'timestamp': None,
            'source': 'database'
        })

    account['source'] = 'database'
    return jsonify(account)


@app.route('/api/account/history')
def api_account_history():
    """
    Get account state history for charting.

    Query params:
        limit (int): Number of records to return (default: 100)

    Returns:
        JSON array of account state snapshots
    """
    limit = request.args.get('limit', default=100, type=int)
    history = get_account_history(limit=limit)

    return jsonify(history)


@app.route('/api/decisions')
def api_decisions():
    """
    Get recent trading decisions.

    Query params:
        limit (int): Number of decisions to return (default: 20)
        coin (str): Filter by specific coin (optional)

    Returns:
        JSON with decisions array and total_count
    """
    limit = request.args.get('limit', default=20, type=int)
    coin = request.args.get('coin', default=None, type=str)

    if coin:
        decisions = get_decisions_by_coin(coin, limit=limit)
    else:
        decisions = get_recent_decisions(limit=limit)

    # Get total count from database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if coin:
            cursor.execute("SELECT COUNT(*) FROM decisions WHERE coin = ?", (coin,))
        else:
            cursor.execute("SELECT COUNT(*) FROM decisions")
        total_count = cursor.fetchone()[0]

    return jsonify({
        'decisions': decisions,
        'total_count': total_count,
        'returned_count': len(decisions)
    })


@app.route('/api/positions')
def api_positions():
    """
    Get positions.

    For LIVE mode with status='open': Queries Hyperliquid API for real-time positions
    Otherwise: Uses database

    Query params:
        status (str): 'open', 'closed', or 'all' (default: 'all')
        limit (int): Number of positions to return (default: 50)

    Returns:
        JSON array of positions
    """
    status = request.args.get('status', default='all', type=str)
    limit = request.args.get('limit', default=50, type=int)

    # If live trading and requesting open positions, get real-time data
    if settings.is_live_trading() and status == 'open':
        try:
            from trading.executor import HyperliquidExecutor
            executor = HyperliquidExecutor(testnet=settings.hyperliquid_testnet)
            live_state = executor.get_account_state()

            if live_state and 'positions' in live_state:
                # Convert Hyperliquid positions to our format
                # Hyperliquid returns assetPositions with nested 'position' objects
                positions = []
                for asset_pos in live_state['positions']:
                    if 'position' in asset_pos:
                        pos = asset_pos['position']
                        size = float(pos.get('szi', 0))
                        entry_px = float(pos.get('entryPx', 0))
                        leverage_obj = pos.get('leverage', {})
                        leverage = float(leverage_obj.get('value', 1)) if isinstance(leverage_obj, dict) else float(leverage_obj)

                        positions.append({
                            'coin': pos.get('coin'),
                            'side': 'long' if size > 0 else 'short',
                            'entry_price': entry_px,
                            'quantity_usd': abs(size) * entry_px,  # Approximate position value
                            'leverage': leverage,
                            'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                            'status': 'open',
                            'source': 'hyperliquid_live'
                        })
                return jsonify(positions)
        except Exception as e:
            print(f"[ERROR] Failed to fetch live positions: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to database

    if status == 'open':
        positions = get_open_positions()
    elif status == 'closed':
        positions = get_closed_positions(limit=limit)
    else:
        positions = get_all_positions(limit=limit)

    return jsonify(positions)


@app.route('/api/status')
def api_status():
    """
    Get current bot status.

    Returns:
        JSON with latest bot status and recent history
    """
    latest = get_latest_bot_status()
    history = get_bot_status_history(limit=10)

    return jsonify({
        'current': latest,
        'history': history
    })


@app.route('/api/stats')
def api_stats():
    """
    Get summary statistics.

    Returns:
        JSON with aggregated stats
    """
    account = get_latest_account_state()
    open_positions = get_open_positions()
    closed_positions = get_closed_positions(limit=100)

    # Calculate stats
    total_trades = len(closed_positions)
    winning_trades = len([p for p in closed_positions if p['realized_pnl'] and p['realized_pnl'] > 0])
    losing_trades = len([p for p in closed_positions if p['realized_pnl'] and p['realized_pnl'] <= 0])

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    total_realized_pnl = sum(p['realized_pnl'] for p in closed_positions if p['realized_pnl'])

    return jsonify({
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': round(win_rate, 2),
        'total_realized_pnl': round(total_realized_pnl, 2),
        'open_positions': len(open_positions),
        'current_balance': account['balance_usd'] if account else 0,
        'current_equity': account['equity_usd'] if account else 0,
        'sharpe_ratio': account['sharpe_ratio'] if account else None
    })


@app.route('/api/debug/database')
def api_debug_database():
    """
    Get raw database entries for debugging.

    Query params:
        table (str): Table name (decisions, account_state, positions, bot_status)
        limit (int): Number of records to return (default: 5)

    Returns:
        JSON with raw database entries
    """
    table = request.args.get('table', default='decisions', type=str)
    limit = request.args.get('limit', default=5, type=int)

    valid_tables = ['decisions', 'account_state', 'positions', 'bot_status']
    if table not in valid_tables:
        return jsonify({
            'error': f'Invalid table. Must be one of: {", ".join(valid_tables)}'
        }), 400

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get table schema
            cursor.execute(f"PRAGMA table_info({table})")
            schema = [dict(row) for row in cursor.fetchall()]

            # Get recent entries
            cursor.execute(f"""
                SELECT * FROM {table}
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            entries = [dict(row) for row in cursor.fetchall()]

            # Get total count
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            total_count = cursor.fetchone()['count']

            return jsonify({
                'table': table,
                'total_count': total_count,
                'limit': limit,
                'schema': schema,
                'entries': entries
            })

    except Exception as e:
        return jsonify({
            'error': f'Database query failed: {str(e)}'
        }), 500


# ============================================================================
# BOT CONTROL
# ============================================================================

# Control file path
BOT_CONTROL_FILE = Path(__file__).parent.parent / "data" / "bot_control.txt"


def read_bot_state():
    """Read the current bot state from control file."""
    if not BOT_CONTROL_FILE.exists():
        return "stopped"
    try:
        return BOT_CONTROL_FILE.read_text().strip()
    except:
        return "stopped"


def write_bot_state(state):
    """Write bot state to control file."""
    BOT_CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
    BOT_CONTROL_FILE.write_text(state)


def is_bot_process_running():
    """Check if the bot process is actually running."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and 'run_analysis_bot.py' in ' '.join(cmdline):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


@app.route('/api/bot/status')
def api_bot_status():
    """
    Get current bot status.

    Returns:
        JSON with bot state and process status
    """
    state = read_bot_state()
    is_running = is_bot_process_running()

    return jsonify({
        'state': state,
        'is_process_running': is_running,
        'control_file': str(BOT_CONTROL_FILE)
    })


@app.route('/api/bot/start', methods=['POST'])
def api_bot_start():
    """
    Start the analysis bot.

    Returns:
        JSON with success status
    """
    try:
        # Check if already running
        if is_bot_process_running():
            return jsonify({
                'success': False,
                'message': 'Bot is already running'
            }), 400

        # Start the bot process
        python_exe = sys.executable
        bot_script = Path(__file__).parent.parent / "run_analysis_bot.py"

        # Set environment variables to ensure unbuffered output
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        # Start in background
        subprocess.Popen(
            [python_exe, str(bot_script), "start"],
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        )

        write_bot_state('running')

        return jsonify({
            'success': True,
            'message': 'Bot started successfully'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to start bot: {str(e)}'
        }), 500


@app.route('/api/bot/pause', methods=['POST'])
def api_bot_pause():
    """
    Pause the analysis bot.

    Returns:
        JSON with success status
    """
    try:
        write_bot_state('paused')

        return jsonify({
            'success': True,
            'message': 'Bot paused'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to pause bot: {str(e)}'
        }), 500


@app.route('/api/bot/resume', methods=['POST'])
def api_bot_resume():
    """
    Resume the paused bot.

    Returns:
        JSON with success status
    """
    try:
        if not is_bot_process_running():
            return jsonify({
                'success': False,
                'message': 'Bot process is not running. Use start instead.'
            }), 400

        write_bot_state('running')

        return jsonify({
            'success': True,
            'message': 'Bot resumed'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to resume bot: {str(e)}'
        }), 500


@app.route('/api/bot/stop', methods=['POST'])
def api_bot_stop():
    """
    Stop the analysis bot.

    Returns:
        JSON with success status
    """
    try:
        write_bot_state('stopped')

        return jsonify({
            'success': True,
            'message': 'Bot stopped'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to stop bot: {str(e)}'
        }), 500


# ============================================================================
# DATABASE MANAGEMENT ROUTES
# ============================================================================

@app.route('/api/user_input', methods=['GET', 'POST', 'DELETE'])
def api_user_input():
    """Get active user input, save new input, or clear input."""
    if request.method == 'GET':
        active_input = get_active_user_input()
        return jsonify(active_input if active_input else {})

    elif request.method == 'POST':
        data = request.json
        message = data.get('message')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
            
        input_id = save_user_input(message)
        return jsonify({
            'success': True,
            'id': input_id,
            'message': 'User input saved'
        })

    elif request.method == 'DELETE':
        # Archive current active input if exists
        active_input = get_active_user_input()
        if active_input:
            archive_user_input(active_input['id'])
            return jsonify({'success': True, 'message': 'User input cleared'})
        return jsonify({'success': True, 'message': 'No active input to clear'})


@app.route('/api/database/status')
def api_database_status():
    """
    Get database statistics and status.

    Returns:
        JSON with database info including:
        - Table counts (decisions, positions, account_state, bot_status)
        - Database file size
        - Latest timestamps
        - Database path
    """
    try:
        status = get_database_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'error': f'Failed to get database status: {str(e)}'
        }), 500


@app.route('/api/database/reset', methods=['POST'])
def api_database_reset():
    """
    Reset (clear) the database.
    
    Query params:
        preserve_schema (bool): If true, keep tables and delete data only
                               If false, drop and recreate tables
                               Default: true

    Returns:
        JSON with success status and new database status
    """
    try:
        # Get preserve_schema parameter (default: True)
        preserve_schema = request.args.get('preserve_schema', 'true').lower() == 'true'
        
        # Perform the reset
        success = reset_database(preserve_schema=preserve_schema)
        
        if not success:
            return jsonify({
                'success': False,
                'message': 'Failed to reset database - check server logs'
            }), 500
        
        # Get new status after reset
        new_status = get_database_status()
        
        return jsonify({
            'success': True,
            'message': 'Database reset successfully',
            'database_status': new_status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to reset database: {str(e)}'
        }), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("="*60)
    print("Trading Bot Dashboard")
    print("="*60)
    print("\nStarting Flask server...")
    print("Dashboard URL: http://localhost:5000")
    print("\nAvailable API endpoints:")
    print("  GET /api/account             - Current account state")
    print("  GET /api/account/history     - Account history")
    print("  GET /api/decisions           - Recent trading decisions")
    print("  GET /api/positions           - Position history")
    print("  GET /api/status              - Bot status")
    print("  GET /api/stats               - Summary statistics")
    print("  GET /api/database/status     - Database statistics")
    print("  POST /api/database/reset     - Reset database (clear all data)")
    print("\nPress Ctrl+C to stop")
    print("="*60)

    app.run(host='0.0.0.0', port=5000, debug=True)
