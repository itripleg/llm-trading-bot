"""
Flask web server for trading bot dashboard.

Provides a simple web interface to monitor:
- Current account balance and PnL
- Active and closed positions
- Recent Claude trading decisions
- Bot status and activity logs
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from pathlib import Path
from werkzeug.utils import secure_filename
import sys
import subprocess
import psutil
import os
import base64

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
    archive_user_input,
    get_active_prompt_preset,
    set_active_prompt_preset,
    get_bot_config,
    update_bot_config
)
from config.settings import settings

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for potential API usage

# Upload configuration
UPLOAD_FOLDER = Path(__file__).parent.parent / 'data' / 'uploads'
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

@app.route('/api/index')
def api_index():
    """
    API Index - List all available endpoints.

    Returns:
        JSON with all API endpoints organized by category
    """
    endpoints = {
        "Account & Portfolio": [
            {
                "path": "/api/account",
                "method": "GET",
                "description": "Get current account state (balance, equity, PnL)",
                "params": {"network": "mainnet|testnet"}
            },
            {
                "path": "/api/account/history",
                "method": "GET",
                "description": "Get account state history for charting",
                "params": {"limit": "int (default: 100)"}
            },
            {
                "path": "/api/stats",
                "method": "GET",
                "description": "Get summary statistics (win rate, total trades, PnL)",
                "params": {}
            }
        ],
        "Trading & Decisions": [
            {
                "path": "/api/decisions",
                "method": "GET",
                "description": "Get recent trading decisions from Claude",
                "params": {"limit": "int (default: 20)", "coin": "str (optional)"}
            },
            {
                "path": "/api/positions",
                "method": "GET",
                "description": "Get positions (open, closed, or all)",
                "params": {
                    "status": "open|closed|all (default: all)",
                    "limit": "int (default: 50)",
                    "network": "mainnet|testnet"
                }
            }
        ],
        "Bot Control": [
            {
                "path": "/api/bot/status",
                "method": "GET",
                "description": "Get current bot status and next cycle info",
                "params": {}
            },
            {
                "path": "/api/bot/start",
                "method": "POST",
                "description": "Start the analysis bot",
                "params": {}
            },
            {
                "path": "/api/bot/pause",
                "method": "POST",
                "description": "Pause the analysis bot",
                "params": {}
            },
            {
                "path": "/api/bot/resume",
                "method": "POST",
                "description": "Resume the paused bot",
                "params": {}
            },
            {
                "path": "/api/bot/stop",
                "method": "POST",
                "description": "Stop the analysis bot",
                "params": {}
            }
        ],
        "Bot Configuration": [
            {
                "path": "/api/bot_config",
                "method": "GET",
                "description": "Get bot configuration settings",
                "params": {}
            },
            {
                "path": "/api/bot_config",
                "method": "POST",
                "description": "Update bot configuration settings",
                "params": {
                    "min_margin_usd": "float",
                    "max_margin_usd": "float",
                    "min_balance_threshold": "float",
                    "execution_interval_seconds": "int (>=10)",
                    "max_open_positions": "int (1-10)"
                }
            },
            {
                "path": "/api/status",
                "method": "GET",
                "description": "Get current bot status with history",
                "params": {}
            }
        ],
        "User Input & Prompts": [
            {
                "path": "/api/user_input",
                "method": "GET",
                "description": "Get active user input message",
                "params": {}
            },
            {
                "path": "/api/user_input",
                "method": "POST",
                "description": "Save new user input (cycle or interrupt)",
                "params": {
                    "message": "str (required)",
                    "message_type": "cycle|interrupt",
                    "image_path": "str (optional)"
                }
            },
            {
                "path": "/api/user_input",
                "method": "DELETE",
                "description": "Clear active user input",
                "params": {}
            },
            {
                "path": "/api/upload_image",
                "method": "POST",
                "description": "Upload an image for chart analysis",
                "params": {"image": "file (png, jpg, jpeg, gif, webp)"}
            },
            {
                "path": "/api/prompt_presets",
                "method": "GET",
                "description": "Get list of available prompt presets",
                "params": {}
            },
            {
                "path": "/api/prompt_presets/active",
                "method": "GET",
                "description": "Get active prompt preset",
                "params": {}
            },
            {
                "path": "/api/prompt_presets/active",
                "method": "POST",
                "description": "Set active prompt preset",
                "params": {"preset_name": "str (required)"}
            },
            {
                "path": "/api/prompt_presets/preview/<preset_name>",
                "method": "GET",
                "description": "Preview full system prompt for a preset",
                "params": {}
            },
            {
                "path": "/api/prompt_presets/sample_user_prompt",
                "method": "GET",
                "description": "Generate sample user prompt showing Claude context",
                "params": {}
            }
        ],
        "Database Management": [
            {
                "path": "/api/database/status",
                "method": "GET",
                "description": "Get database statistics and status",
                "params": {}
            },
            {
                "path": "/api/database/reset",
                "method": "POST",
                "description": "Reset (clear) the database",
                "params": {"preserve_schema": "bool (default: true)"}
            },
            {
                "path": "/api/debug/database",
                "method": "GET",
                "description": "Get raw database entries for debugging",
                "params": {
                    "table": "decisions|account_state|positions|bot_status",
                    "limit": "int (default: 5)"
                }
            }
        ]
    }

    # Count total endpoints
    total_endpoints = sum(len(category) for category in endpoints.values())

    # Get all endpoint paths for quick reference
    all_paths = []
    for category in endpoints.values():
        for endpoint in category:
            all_paths.append(f"{endpoint['method']} {endpoint['path']}")

    return jsonify({
        "version": "1.0.0",
        "name": "Alpha Arena Mini API",
        "description": "Trading bot dashboard and control API",
        "base_url": "http://localhost:5000",
        "total_endpoints": total_endpoints,
        "categories": list(endpoints.keys()),
        "endpoints": endpoints,
        "all_paths": sorted(all_paths)
    })


@app.route('/api/account')
def api_account():
    """
    Get current account state.

    For LIVE mode: Queries Hyperliquid API directly for real-time data
    For PAPER mode: Uses latest database snapshot

    Query params:
        network (str): 'mainnet' or 'testnet' (overrides settings if provided)

    Returns:
        JSON with balance, equity, PnL, positions count
    """
    # Get network parameter from query string
    network = request.args.get('network', default='mainnet', type=str)
    is_testnet = (network == 'testnet')

    # If live trading, get real-time data from Hyperliquid
    if settings.is_live_trading():
        try:
            from trading.executor import HyperliquidExecutor
            executor = HyperliquidExecutor(testnet=is_testnet)
            live_state = executor.get_account_state()

            if live_state:
                # Get realized PnL from all closed positions (Hyperliquid doesn't track this)
                from web.database import get_total_realized_pnl
                realized_pnl = get_total_realized_pnl()

                return jsonify({
                    'balance_usd': live_state.get('account_value', 0.0),
                    'equity_usd': live_state.get('account_value', 0.0),
                    'unrealized_pnl': live_state.get('unrealized_pnl', 0.0),
                    'realized_pnl': realized_pnl,
                    'total_pnl': live_state.get('unrealized_pnl', 0.0) + realized_pnl,
                    'num_positions': len(live_state.get('positions', [])),
                    'timestamp': live_state.get('timestamp'),
                    'source': f'hyperliquid_live_{network}'
                })
        except Exception as e:
            print(f"[ERROR] Failed to fetch live Hyperliquid data from {network}: {e}")
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
        network (str): 'mainnet' or 'testnet' (overrides settings if provided)

    Returns:
        JSON array of positions
    """
    status = request.args.get('status', default='all', type=str)
    limit = request.args.get('limit', default=50, type=int)
    network = request.args.get('network', default='mainnet', type=str)
    is_testnet = (network == 'testnet')

    # If live trading and requesting open positions, get real-time data
    if settings.is_live_trading() and status == 'open':
        try:
            from trading.executor import HyperliquidExecutor
            executor = HyperliquidExecutor(testnet=is_testnet)
            live_state = executor.get_account_state()

            if live_state and 'positions' in live_state:
                # Convert Hyperliquid positions to our format
                # Hyperliquid returns assetPositions with nested 'position' objects
                # Get database positions to fetch entry timestamps
                db_positions = get_open_positions()
                db_positions_map = {p['coin']: p for p in db_positions}

                positions = []
                for asset_pos in live_state['positions']:
                    if 'position' in asset_pos:
                        pos = asset_pos['position']
                        coin = pos.get('coin')
                        size = float(pos.get('szi', 0))
                        entry_px = float(pos.get('entryPx', 0))
                        leverage_obj = pos.get('leverage', {})
                        leverage = float(leverage_obj.get('value', 1)) if isinstance(leverage_obj, dict) else float(leverage_obj)

                        # Get entry_time from database if available
                        entry_time = None
                        if coin in db_positions_map:
                            entry_time = db_positions_map[coin].get('entry_time')

                        positions.append({
                            'coin': coin,
                            'side': 'long' if size > 0 else 'short',
                            'entry_price': entry_px,
                            'quantity_usd': abs(size) * entry_px,  # Approximate position value
                            'leverage': leverage,
                            'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                            'entry_time': entry_time,  # From database
                            'status': 'open',
                            'source': f'hyperliquid_live_{network}'
                        })
                return jsonify(positions)
        except Exception as e:
            print(f"[ERROR] Failed to fetch live positions from {network}: {e}")
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
        JSON with bot state, process status, and next cycle info
    """
    state = read_bot_state()
    is_running = is_bot_process_running()

    # Get next cycle time saved by the bot (more accurate than calculating)
    next_cycle_time = None
    cycle_interval = None

    try:
        # Read the next_cycle_time that the bot saves after each cycle
        from web.database import get_bot_setting
        next_cycle_time = get_bot_setting('next_cycle_time')

        config = get_bot_config()
        cycle_interval = config['execution_interval_seconds']

    except Exception as e:
        print(f"[WARN] Could not get next cycle time: {e}")

    return jsonify({
        'state': state,
        'is_process_running': is_running,
        'control_file': str(BOT_CONTROL_FILE),
        'cycle_interval_seconds': cycle_interval,
        'next_cycle_time': next_cycle_time
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
        message_type = data.get('message_type', 'cycle')  # 'cycle' or 'interrupt'
        image_path = data.get('image_path')  # Optional path to uploaded image

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        if message_type not in ['cycle', 'interrupt']:
            return jsonify({'error': 'message_type must be "cycle" or "interrupt"'}), 400

        input_id = save_user_input(message, message_type, image_path)

        # If interrupt type (direct query), trigger immediate response
        if message_type == 'interrupt':
            # Import here to avoid circular dependency
            from llm.direct_query import handle_direct_query

            try:
                # Get bot's immediate response to the query
                response = handle_direct_query(message, image_path)

                return jsonify({
                    'success': True,
                    'id': input_id,
                    'message': 'Query sent',
                    'message_type': message_type,
                    'response': response  # Return bot's answer immediately
                })
            except Exception as e:
                print(f"[ERROR] Direct query failed: {e}")
                return jsonify({
                    'success': True,
                    'id': input_id,
                    'message': 'Query saved but response failed',
                    'message_type': message_type,
                    'error': str(e)
                })

        return jsonify({
            'success': True,
            'id': input_id,
            'message': 'User input saved',
            'message_type': message_type
        })

    elif request.method == 'DELETE':
        # Archive current active input if exists
        active_input = get_active_user_input()
        if active_input:
            archive_user_input(active_input['id'])
            return jsonify({'success': True, 'message': 'User input cleared'})
        return jsonify({'success': True, 'message': 'No active input to clear'})


@app.route('/api/upload_image', methods=['POST'])
def api_upload_image():
    """Upload an image for chart analysis."""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        from datetime import datetime
        # Create unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"chart_{timestamp}.{ext}"
        filepath = app.config['UPLOAD_FOLDER'] / filename

        file.save(str(filepath))

        return jsonify({
            'success': True,
            'filename': filename,
            'path': str(filepath)
        })
    else:
        return jsonify({'error': 'Invalid file type. Allowed: png, jpg, jpeg, gif, webp'}), 400


@app.route('/api/prompt_presets', methods=['GET'])
def api_get_prompt_presets():
    """Get list of available prompt presets."""
    try:
        from llm.prompt_presets import list_presets, get_preset_description

        presets_list = list_presets()
        presets_with_descriptions = []

        for key, name in presets_list.items():
            presets_with_descriptions.append({
                'key': key,
                'name': name,
                'description': get_preset_description(key)
            })

        active_preset = get_active_prompt_preset()

        return jsonify({
            'presets': presets_with_descriptions,
            'active_preset': active_preset
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/prompt_presets/active', methods=['GET', 'POST'])
def api_active_prompt_preset():
    """Get or set the active prompt preset."""
    if request.method == 'GET':
        active_preset = get_active_prompt_preset()
        return jsonify({'active_preset': active_preset})

    elif request.method == 'POST':
        data = request.json
        preset_name = data.get('preset_name')

        if not preset_name:
            return jsonify({'error': 'preset_name is required'}), 400

        # Validate preset exists
        from llm.prompt_presets import list_presets
        available_presets = list_presets()

        if preset_name not in available_presets:
            return jsonify({
                'error': f'Invalid preset. Available: {", ".join(available_presets.keys())}'
            }), 400

        # Set the new preset
        success = set_active_prompt_preset(preset_name)

        if success:
            return jsonify({
                'success': True,
                'active_preset': preset_name,
                'message': f'Preset changed to {available_presets[preset_name]}'
            })
        else:
            return jsonify({'error': 'Failed to set preset'}), 500


@app.route('/api/prompt_presets/preview/<preset_name>', methods=['GET'])
def api_preview_prompt_preset(preset_name):
    """Generate and return the full system prompt for a preset."""
    try:
        from llm.prompts import TradingConfig, PromptBuilder
        from llm.prompt_presets import list_presets

        available_presets = list_presets()

        if preset_name not in available_presets:
            return jsonify({
                'error': f'Invalid preset. Available: {", ".join(available_presets.keys())}'
            }), 400

        # Create config with the preset
        trading_config = TradingConfig(
            exchange_name=settings.exchange_name if hasattr(settings, 'exchange_name') else "Hyperliquid",
            min_position_size_usd=settings.min_position_size_usd if hasattr(settings, 'min_position_size_usd') else 10.0,
            max_leverage=settings.max_leverage if hasattr(settings, 'max_leverage') else 10.0,
            preset_name=preset_name,
        )

        # Generate the system prompt
        prompt_builder = PromptBuilder(config=trading_config)
        system_prompt = prompt_builder.get_system_prompt()

        return jsonify({
            'preset_name': preset_name,
            'preset_display_name': available_presets[preset_name],
            'system_prompt': system_prompt
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/prompt_presets/sample_user_prompt', methods=['GET'])
def api_sample_user_prompt():
    """Generate a sample user prompt showing what context Claude receives."""
    try:
        from llm.prompts import TradingConfig, PromptBuilder
        import pandas as pd
        from datetime import datetime, timedelta

        # Get active preset
        active_preset = get_active_prompt_preset()

        # Create config
        trading_config = TradingConfig(
            exchange_name=settings.exchange_name if hasattr(settings, 'exchange_name') else "Hyperliquid",
            min_position_size_usd=settings.min_position_size_usd if hasattr(settings, 'min_position_size_usd') else 10.0,
            max_leverage=settings.max_leverage if hasattr(settings, 'max_leverage') else 10.0,
            preset_name=active_preset,
        )

        prompt_builder = PromptBuilder(config=trading_config)

        # Create sample market data
        sample_market_data = {
            'BTC/USDC:USDC': {
                'current_price': 45000.00,
                'indicators': pd.DataFrame({
                    'timestamp': pd.date_range(end=datetime.now(), periods=50, freq='5min'),
                    'close': [45000 + (i * 10) for i in range(50)],
                    'ema_20': [44950 + (i * 10) for i in range(50)],
                    'rsi_7': [50 + (i % 20) for i in range(50)],
                    'macd': [0.5 + (i * 0.01) for i in range(50)],
                }),
                'funding_rate': 0.0001,
                'open_interest': 1500000000
            },
            'ETH/USDC:USDC': {
                'current_price': 2500.00,
                'indicators': pd.DataFrame({
                    'timestamp': pd.date_range(end=datetime.now(), periods=50, freq='5min'),
                    'close': [2500 + (i * 5) for i in range(50)],
                    'ema_20': [2490 + (i * 5) for i in range(50)],
                    'rsi_7': [45 + (i % 15) for i in range(50)],
                    'macd': [0.3 + (i * 0.005) for i in range(50)],
                }),
                'funding_rate': 0.00005,
                'open_interest': 800000000
            }
        }

        # Create sample account state
        sample_account_state = {
            'available_cash': 100.00,
            'total_value': 150.00,
            'total_return_pct': 50.0,
            'sharpe_ratio': 1.2,
            'positions': [
                {
                    'coin': 'BTC/USDC:USDC',
                    'side': 'long',
                    'entry_price': 44000.00,
                    'current_price': 45000.00,
                    'quantity_usd': 50.00,
                    'leverage': 5.0,
                    'unrealized_pnl': 5.68,
                    'profit_target': 46000.00,
                    'stop_loss': 43500.00
                }
            ],
            'trade_history': get_closed_positions(limit=10),
            'recent_decisions': get_recent_decisions(limit=5)
        }

        # Build sample user prompt
        user_prompt = prompt_builder.build_trading_prompt(
            market_data=sample_market_data,
            account_state=sample_account_state,
            minutes_since_start=120,
            user_guidance=None,
            leverage_limits={'BTC/USDC:USDC': 50, 'ETH/USDC:USDC': 25}
        )

        return jsonify({
            'user_prompt': user_prompt,
            'note': 'This is a sample showing the format. Live prompts include real-time market data.'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bot_config', methods=['GET', 'POST'])
def api_bot_config():
    """Get or update bot configuration settings."""
    if request.method == 'GET':
        try:
            config = get_bot_config()
            return jsonify({
                'success': True,
                'config': config
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            data = request.json
            config_updates = {}

            # Validate and update each field
            if 'min_margin_usd' in data:
                val = float(data['min_margin_usd'])
                if val <= 0:
                    return jsonify({'error': 'min_margin_usd must be > 0'}), 400
                config_updates['min_margin_usd'] = val

            if 'min_balance_threshold' in data:
                val = float(data['min_balance_threshold'])
                if val < 0:
                    return jsonify({'error': 'min_balance_threshold must be >= 0'}), 400
                config_updates['min_balance_threshold'] = val

            if 'max_margin_usd' in data:
                val = float(data['max_margin_usd'])
                if val <= 0:
                    return jsonify({'error': 'max_margin_usd must be > 0'}), 400
                config_updates['max_margin_usd'] = val

            if 'execution_interval_seconds' in data:
                val = int(data['execution_interval_seconds'])
                if val < 10:
                    return jsonify({'error': 'execution_interval_seconds must be >= 10'}), 400
                config_updates['execution_interval_seconds'] = val

            if 'max_open_positions' in data:
                val = int(data['max_open_positions'])
                if val < 1 or val > 10:
                    return jsonify({'error': 'max_open_positions must be between 1 and 10'}), 400
                config_updates['max_open_positions'] = val

            if not config_updates:
                return jsonify({'error': 'No valid configuration updates provided'}), 400

            success = update_bot_config(config_updates)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Configuration updated successfully',
                    'config': get_bot_config()
                })
            else:
                return jsonify({'error': 'Failed to update configuration'}), 500

        except ValueError as e:
            return jsonify({'error': f'Invalid value: {str(e)}'}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500


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
    print("\nAPI Documentation:")
    print("  GET /api/index               - Complete API index (all endpoints)")
    print("\nKey API endpoints:")
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
