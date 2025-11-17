"use client";

import { useState, useEffect, useCallback } from "react";
import type { BotStatus, BotControlResponse } from "../types";

const POLLING_INTERVAL = 3000; // 3 seconds - status needs to be frequent

export function useBotStatus() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch("/api/llm-bot/status");
      if (!response.ok) {
        throw new Error(`Failed to fetch status: ${response.statusText}`);
      }
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch status");
      console.error("Error fetching bot status:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, POLLING_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  return { status, loading, error, refetch: fetchStatus };
}

export function useBotControls() {
  const [controlling, setControlling] = useState(false);

  const startBot = useCallback(async (): Promise<BotControlResponse> => {
    setControlling(true);
    try {
      const response = await fetch("/api/llm-bot/controls/start", {
        method: "POST",
      });
      const data = await response.json();
      return data;
    } catch (err) {
      return {
        success: false,
        message: err instanceof Error ? err.message : "Failed to start bot",
      };
    } finally {
      setControlling(false);
    }
  }, []);

  const stopBot = useCallback(async (): Promise<BotControlResponse> => {
    setControlling(true);
    try {
      const response = await fetch("/api/llm-bot/controls/stop", {
        method: "POST",
      });
      const data = await response.json();
      return data;
    } catch (err) {
      return {
        success: false,
        message: err instanceof Error ? err.message : "Failed to stop bot",
      };
    } finally {
      setControlling(false);
    }
  }, []);

  const emergencyStop = useCallback(async (): Promise<BotControlResponse> => {
    setControlling(true);
    try {
      const response = await fetch("/api/llm-bot/controls/emergency", {
        method: "POST",
      });
      const data = await response.json();
      return data;
    } catch (err) {
      return {
        success: false,
        message: err instanceof Error ? err.message : "Emergency stop failed",
      };
    } finally {
      setControlling(false);
    }
  }, []);

  return { startBot, stopBot, emergencyStop, controlling };
}
