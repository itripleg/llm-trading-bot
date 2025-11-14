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
    get_bot_status_history
)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for potential API usage

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

    Returns:
        JSON with balance, equity, PnL, positions count
    """
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
            'timestamp': None
        })

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
        JSON array of trading decisions
    """
    limit = request.args.get('limit', default=20, type=int)
    coin = request.args.get('coin', default=None, type=str)

    if coin:
        decisions = get_decisions_by_coin(coin, limit=limit)
    else:
        decisions = get_recent_decisions(limit=limit)

    return jsonify(decisions)


@app.route('/api/positions')
def api_positions():
    """
    Get positions.

    Query params:
        status (str): 'open', 'closed', or 'all' (default: 'all')
        limit (int): Number of positions to return (default: 50)

    Returns:
        JSON array of positions
    """
    status = request.args.get('status', default='all', type=str)
    limit = request.args.get('limit', default=50, type=int)

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
    print("  GET /api/account          - Current account state")
    print("  GET /api/account/history  - Account history")
    print("  GET /api/decisions        - Recent trading decisions")
    print("  GET /api/positions        - Position history")
    print("  GET /api/status           - Bot status")
    print("  GET /api/stats            - Summary statistics")
    print("\nPress Ctrl+C to stop")
    print("="*60)

    app.run(host='0.0.0.0', port=5000, debug=True)
