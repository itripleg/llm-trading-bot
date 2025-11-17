"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Brain, TrendingUp, TrendingDown, Minus, X } from "lucide-react";
import { useBotDecisions } from "../hooks/useBotDecisions";
import type { BotDecision } from "../types";

function DecisionCard({ decision }: { decision: BotDecision }) {
  const getSignalColor = (signal: string) => {
    switch (signal) {
      case "buy_to_enter":
        return "bg-green-500/10 text-green-500 border-green-500/50";
      case "sell_to_enter":
        return "bg-red-500/10 text-red-500 border-red-500/50";
      case "hold":
        return "bg-blue-500/10 text-blue-500 border-blue-500/50";
      case "close":
        return "bg-yellow-500/10 text-yellow-500 border-yellow-500/50";
      default:
        return "bg-gray-500/10 text-gray-500 border-gray-500/50";
    }
  };

  const getSignalIcon = (signal: string) => {
    switch (signal) {
      case "buy_to_enter":
        return <TrendingUp className="w-3 h-3" />;
      case "sell_to_enter":
        return <TrendingDown className="w-3 h-3" />;
      case "hold":
        return <Minus className="w-3 h-3" />;
      case "close":
        return <X className="w-3 h-3" />;
      default:
        return null;
    }
  };

  const confidenceColor = decision.confidence >= 0.7
    ? "text-green-500"
    : decision.confidence >= 0.5
    ? "text-yellow-500"
    : "text-red-500";

  return (
    <div className="p-4 border border-border/30 rounded-lg hover:border-primary/30 transition-colors bg-card/50">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <h4 className="font-semibold">{decision.coin}</h4>
          <Badge variant="outline" className={getSignalColor(decision.signal)}>
            <span className="flex items-center gap-1">
              {getSignalIcon(decision.signal)}
              {decision.signal.replace("_", " ").toUpperCase()}
            </span>
          </Badge>
        </div>
        <span className="text-xs text-muted-foreground">
          {new Date(decision.timestamp).toLocaleString()}
        </span>
      </div>

      {/* Details */}
      <div className="grid grid-cols-3 gap-3 mb-3 text-sm">
        <div>
          <p className="text-xs text-muted-foreground">Size</p>
          <p className="font-mono">${decision.quantity_usd.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Leverage</p>
          <p className="font-mono">{decision.leverage}x</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Confidence</p>
          <p className={`font-mono font-semibold ${confidenceColor}`}>
            {(decision.confidence * 100).toFixed(0)}%
          </p>
        </div>
      </div>

      {/* Exit Plan */}
      {(decision.profit_target || decision.stop_loss) && (
        <div className="mb-3 text-sm">
          <p className="text-xs text-muted-foreground mb-1">Exit Plan</p>
          <div className="flex gap-4">
            {decision.profit_target && (
              <div>
                <span className="text-xs text-muted-foreground">Target: </span>
                <span className="font-mono text-green-500">
                  ${decision.profit_target.toFixed(2)}
                </span>
              </div>
            )}
            {decision.stop_loss && (
              <div>
                <span className="text-xs text-muted-foreground">Stop: </span>
                <span className="font-mono text-red-500">
                  ${decision.stop_loss.toFixed(2)}
                </span>
              </div>
            )}
          </div>
          {decision.invalidation_condition && (
            <p className="text-xs text-muted-foreground mt-1">
              Invalidation: {decision.invalidation_condition}
            </p>
          )}
        </div>
      )}

      {/* Justification */}
      <div className="text-sm">
        <p className="text-xs text-muted-foreground mb-1">Analysis</p>
        <p className="text-muted-foreground">{decision.justification}</p>
      </div>
    </div>
  );
}

export function DecisionsFeed({ limit = 10, coin }: { limit?: number; coin?: string }) {
  const { decisions, loading, error } = useBotDecisions(limit, coin);

  if (loading) {
    return (
      <Card className="unified-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-primary" />
            Trading Decisions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="unified-card border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-destructive" />
            Trading Decisions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive text-sm">{error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="unified-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-primary" />
          Trading Decisions
          {coin && <span className="text-sm text-muted-foreground ml-2">({coin})</span>}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {decisions.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            No trading decisions yet
          </div>
        ) : (
          <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
            {decisions.map((decision) => (
              <DecisionCard key={decision.id} decision={decision} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
