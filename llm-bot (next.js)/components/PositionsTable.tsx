"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, TrendingDown } from "lucide-react";
import { useBotPositions } from "../hooks/useBotPositions";
import type { BotPosition } from "../types";

function PositionRow({ position }: { position: BotPosition }) {
  const isOpen = position.status === "open";
  const isPnlPositive = isOpen
    ? (position.unrealized_pnl || 0) >= 0
    : (position.realized_pnl || 0) >= 0;

  const pnl = isOpen ? position.unrealized_pnl : position.realized_pnl;

  return (
    <div className="grid grid-cols-6 gap-2 items-center py-3 px-4 border-b border-border/30 hover:bg-accent/10 transition-colors">
      {/* Coin */}
      <div className="font-semibold">{position.coin}</div>

      {/* Side */}
      <div>
        <Badge
          variant="outline"
          className={
            position.side === "long"
              ? "bg-green-500/10 text-green-500 border-green-500/50"
              : "bg-red-500/10 text-red-500 border-red-500/50"
          }
        >
          {position.side.toUpperCase()}
        </Badge>
      </div>

      {/* Size & Leverage */}
      <div>
        <div className="font-mono text-sm">${(position.quantity_usd ?? 0).toFixed(2)}</div>
        <div className="text-xs text-muted-foreground">{position.leverage ?? 1}x</div>
      </div>

      {/* Entry Price */}
      <div className="font-mono text-sm">
        ${(position.entry_price ?? 0).toFixed(2)}
      </div>

      {/* Current/Exit Price */}
      <div className="font-mono text-sm">
        {isOpen ? (
          position.current_price ? `$${(position.current_price ?? 0).toFixed(2)}` : "..."
        ) : (
          position.exit_price ? `$${(position.exit_price ?? 0).toFixed(2)}` : "N/A"
        )}
      </div>

      {/* P&L */}
      <div className={`font-semibold text-right ${isPnlPositive ? "text-green-500" : "text-red-500"}`}>
        <div className="flex items-center justify-end gap-1">
          {pnl !== null && pnl !== undefined ? (
            <>
              ${Math.abs(pnl).toFixed(2)}
              {isPnlPositive ? (
                <TrendingUp className="w-4 h-4" />
              ) : (
                <TrendingDown className="w-4 h-4" />
              )}
            </>
          ) : (
            "N/A"
          )}
        </div>
      </div>
    </div>
  );
}

export function PositionsTable() {
  const [activeTab, setActiveTab] = useState<"open" | "closed">("open");
  const { positions: openPositions, loading: loadingOpen } = useBotPositions("open");
  const { positions: closedPositions, loading: loadingClosed } = useBotPositions("closed");

  const positions = activeTab === "open" ? openPositions : closedPositions;
  const loading = activeTab === "open" ? loadingOpen : loadingClosed;

  return (
    <Card className="unified-card">
      <CardHeader>
        <CardTitle>Positions</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "open" | "closed")}>
          <TabsList className="grid w-full grid-cols-2 mb-4">
            <TabsTrigger value="open">
              Open ({openPositions.length})
            </TabsTrigger>
            <TabsTrigger value="closed">
              Closed ({closedPositions.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="open" className="mt-0">
            {loading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-16" />
                ))}
              </div>
            ) : positions.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No open positions
              </div>
            ) : (
              <div>
                {/* Header */}
                <div className="grid grid-cols-6 gap-2 px-4 py-2 text-xs font-semibold text-muted-foreground border-b border-border">
                  <div>COIN</div>
                  <div>SIDE</div>
                  <div>SIZE</div>
                  <div>ENTRY</div>
                  <div>CURRENT</div>
                  <div className="text-right">UNREALIZED P&L</div>
                </div>
                {/* Rows */}
                {positions.map((position) => (
                  <PositionRow key={position.id} position={position} />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="closed" className="mt-0">
            {loading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-16" />
                ))}
              </div>
            ) : positions.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No closed positions
              </div>
            ) : (
              <div>
                {/* Header */}
                <div className="grid grid-cols-6 gap-2 px-4 py-2 text-xs font-semibold text-muted-foreground border-b border-border">
                  <div>COIN</div>
                  <div>SIDE</div>
                  <div>SIZE</div>
                  <div>ENTRY</div>
                  <div>EXIT</div>
                  <div className="text-right">REALIZED P&L</div>
                </div>
                {/* Rows */}
                {positions.map((position) => (
                  <PositionRow key={position.id} position={position} />
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
