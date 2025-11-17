"use client";

import { useEffect, useState } from "react";
import { Container } from "@/components/craft";
import { AccountOverview } from "./components/AccountOverview";
import { BotStatus } from "./components/BotStatus";
import { PositionsTable } from "./components/PositionsTable";
import { DecisionsFeed } from "./components/DecisionsFeed";

export default function LLMBotDashboard() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <Container className="py-8 space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-primary via-primary/80 to-primary/60 bg-clip-text text-transparent">
          LLM Trading Bot
        </h1>
        <p className="text-muted-foreground">
          Monitor Claude's autonomous trading performance on Hyperliquid
        </p>
      </div>

      {/* Status */}
      <BotStatus />

      {/* Account Overview */}
      <AccountOverview />

      {/* Positions and Decisions */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <PositionsTable />
        <DecisionsFeed limit={10} />
      </div>

      {/* Footer Info */}
      <div className="mt-8 p-4 rounded-lg bg-card/50 border border-border/50">
        <p className="text-xs text-muted-foreground">
          <strong>Architecture:</strong> The Python bot posts data to{" "}
          <code className="px-1 py-0.5 bg-muted rounded text-xs">/api/llm-bot/ingest/*</code>
          {" "}endpoints, which stores it in Firebase. This dashboard reads from Firebase for real-time monitoring.
          The bot can run anywhere (local, cloud, VPS) and just needs the API key.
        </p>
      </div>
    </Container>
  );
}
