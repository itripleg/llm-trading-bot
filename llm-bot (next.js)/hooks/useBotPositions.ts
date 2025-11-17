"use client";

import { useState, useEffect, useCallback } from "react";
import type { BotPosition } from "../types";

const POLLING_INTERVAL = 10000; // 10 seconds

export function useBotPositions(status: "open" | "closed" | "all" = "all") {
  const [positions, setPositions] = useState<BotPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPositions = useCallback(async () => {
    try {
      const response = await fetch(`/api/llm-bot/positions?status=${status}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch positions: ${response.statusText}`);
      }
      const data = await response.json();
      setPositions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch positions");
      console.error("Error fetching bot positions:", err);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, POLLING_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchPositions]);

  return { positions, loading, error, refetch: fetchPositions };
}
