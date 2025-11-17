/**
 * TypeScript types for LLM Trading Bot
 * Based on SQLite database schema from llm-trading-bot/web/database.py
 */

export interface BotAccountState {
  balance_usd: number;
  equity_usd: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
  sharpe_ratio: number | null;
  num_positions: number;
  timestamp: string | null;
}

export interface BotPosition {
  id: number;
  coin: string;
  side: "long" | "short";
  quantity_usd: number;
  leverage: number;
  entry_price: number;
  entry_time: string;
  exit_price: number | null;
  exit_time: string | null;
  realized_pnl: number | null;
  status: "open" | "closed";
  current_price?: number;
  unrealized_pnl?: number;
}

export interface BotDecision {
  id: number;
  timestamp: string;
  coin: string;
  signal: "buy_to_enter" | "sell_to_enter" | "hold" | "close";
  quantity_usd: number;
  leverage: number;
  confidence: number;
  profit_target: number | null;
  stop_loss: number | null;
  invalidation_condition: string | null;
  justification: string;
  raw_response: string | null;
  created_at: string;
}

export interface BotStatus {
  id: number;
  timestamp: string;
  status: "running" | "stopped" | "error" | "paused";
  message: string;
  trades_today: number;
  pnl_today: number;
  created_at: string;
}

export interface BotControlResponse {
  success: boolean;
  message: string;
  status?: string;
}

export interface AccountHistoryPoint {
  timestamp: string;
  balance_usd: number;
  equity_usd: number;
  total_pnl: number;
}

export type TradingMode = "paper" | "live";

export interface BotConfig {
  mode: TradingMode;
  flask_url: string;
  polling_interval: number; // milliseconds
}
