"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, TrendingDown, DollarSign, Activity } from "lucide-react";
import { useBotAccount } from "../hooks/useBotAccount";

export function AccountOverview() {
  const { account, loading, error } = useBotAccount();

  if (loading) {
    return (
      <Card className="unified-card">
        <CardHeader>
          <CardTitle>Account Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="unified-card border-destructive">
        <CardHeader>
          <CardTitle>Account Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive text-sm">
            {error}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!account) return null;

  // Add safety checks for undefined values
  const balance = account.balance_usd ?? 0;
  const equity = account.equity_usd ?? 0;
  const totalPnl = account.total_pnl ?? 0;
  const unrealizedPnl = account.unrealized_pnl ?? 0;
  const realizedPnl = account.realized_pnl ?? 0;

  const isProfit = totalPnl >= 0;
  const pnlPercentage = balance > 0
    ? ((totalPnl / balance) * 100).toFixed(2)
    : "0.00";

  return (
    <Card className="unified-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-primary" />
          Account Overview
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Balance */}
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">Balance</p>
            <p className="text-2xl font-bold">
              ${balance.toFixed(2)}
            </p>
          </div>

          {/* Equity */}
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">Equity</p>
            <p className="text-2xl font-bold">
              ${equity.toFixed(2)}
            </p>
          </div>

          {/* Total PnL */}
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">Total P&L</p>
            <div className="flex items-center gap-2">
              <p className={`text-2xl font-bold ${isProfit ? "text-green-500" : "text-red-500"}`}>
                ${totalPnl.toFixed(2)}
              </p>
              {isProfit ? (
                <TrendingUp className="w-5 h-5 text-green-500" />
              ) : (
                <TrendingDown className="w-5 h-5 text-red-500" />
              )}
            </div>
            <p className={`text-xs ${isProfit ? "text-green-500" : "text-red-500"}`}>
              {isProfit ? "+" : ""}{pnlPercentage}%
            </p>
          </div>

          {/* Sharpe Ratio */}
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground flex items-center gap-1">
              <Activity className="w-4 h-4" />
              Sharpe Ratio
            </p>
            <p className="text-2xl font-bold">
              {account.sharpe_ratio !== null ? account.sharpe_ratio.toFixed(2) : "N/A"}
            </p>
            <p className="text-xs text-muted-foreground">
              {account.num_positions} position{account.num_positions !== 1 ? "s" : ""}
            </p>
          </div>
        </div>

        {/* Unrealized vs Realized PnL */}
        <div className="mt-6 pt-4 border-t border-border/50 grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-muted-foreground">Unrealized P&L</p>
            <p className={`text-lg font-semibold ${unrealizedPnl >= 0 ? "text-green-500" : "text-red-500"}`}>
              ${unrealizedPnl.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Realized P&L</p>
            <p className={`text-lg font-semibold ${realizedPnl >= 0 ? "text-green-500" : "text-red-500"}`}>
              ${realizedPnl.toFixed(2)}
            </p>
          </div>
        </div>

        {account.timestamp && (
          <p className="text-xs text-muted-foreground mt-4">
            Last updated: {new Date(account.timestamp).toLocaleString()}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
