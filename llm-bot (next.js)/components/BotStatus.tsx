"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Bot, AlertCircle, CheckCircle, Pause, XCircle } from "lucide-react";
import { useBotStatus } from "../hooks/useBotStatus";

export function BotStatus() {
  const { status, loading, error } = useBotStatus();

  const getStatusColor = (statusValue?: string) => {
    switch (statusValue) {
      case "running":
        return "bg-green-500/10 text-green-500 border-green-500/50";
      case "stopped":
        return "bg-gray-500/10 text-gray-500 border-gray-500/50";
      case "paused":
        return "bg-yellow-500/10 text-yellow-500 border-yellow-500/50";
      case "error":
        return "bg-red-500/10 text-red-500 border-red-500/50";
      default:
        return "bg-gray-500/10 text-gray-500 border-gray-500/50";
    }
  };

  const getStatusIcon = (statusValue?: string) => {
    switch (statusValue) {
      case "running":
        return <CheckCircle className="w-4 h-4" />;
      case "stopped":
        return <XCircle className="w-4 h-4" />;
      case "paused":
        return <Pause className="w-4 h-4" />;
      case "error":
        return <AlertCircle className="w-4 h-4" />;
      default:
        return <Bot className="w-4 h-4" />;
    }
  };

  if (loading) {
    return (
      <Card className="unified-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-primary" />
            Bot Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="animate-pulse">
              Loading...
            </Badge>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !status) {
    return (
      <Card className="unified-card border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-destructive" />
            Bot Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-destructive" />
            <Badge variant="outline" className="bg-destructive/10 text-destructive border-destructive/50">
              Disconnected
            </Badge>
            <p className="text-sm text-muted-foreground ml-2">
              {error || "Cannot connect to bot"}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const isProfitToday = status.pnl_today >= 0;

  return (
    <Card className="unified-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-primary" />
          Bot Status
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Badge variant="outline" className={getStatusColor(status.status)}>
              <span className="flex items-center gap-2">
                {getStatusIcon(status.status)}
                {status.status.toUpperCase()}
              </span>
            </Badge>
            <p className="text-sm text-muted-foreground">{status.message}</p>
          </div>

          <div className="grid grid-cols-2 gap-4 pt-2">
            <div>
              <p className="text-xs text-muted-foreground">Trades Today</p>
              <p className="text-lg font-semibold">{status.trades_today}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">P&L Today</p>
              <p className={`text-lg font-semibold ${isProfitToday ? "text-green-500" : "text-red-500"}`}>
                ${status.pnl_today.toFixed(2)}
              </p>
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            Last check: {new Date(status.timestamp).toLocaleTimeString()}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
