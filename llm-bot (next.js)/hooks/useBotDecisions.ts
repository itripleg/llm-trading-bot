"use client";

import { useState, useEffect, useCallback } from "react";
import type { BotDecision } from "../types";

const POLLING_INTERVAL = 5000; // 5 seconds - decisions update frequently

export function useBotDecisions(limit: number = 20, coin?: string) {
  const [decisions, setDecisions] = useState<BotDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDecisions = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: limit.toString() });
      if (coin) params.append("coin", coin);

      const response = await fetch(`/api/llm-bot/decisions?${params}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch decisions: ${response.statusText}`);
      }
      const data = await response.json();
      setDecisions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch decisions");
      console.error("Error fetching bot decisions:", err);
    } finally {
      setLoading(false);
    }
  }, [limit, coin]);

  useEffect(() => {
    fetchDecisions();
    const interval = setInterval(fetchDecisions, POLLING_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchDecisions]);

  return { decisions, loading, error, refetch: fetchDecisions };
}
