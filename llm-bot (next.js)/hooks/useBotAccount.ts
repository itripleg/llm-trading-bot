"use client";

import { useState, useEffect, useCallback } from "react";
import type { BotAccountState, AccountHistoryPoint } from "../types";

const POLLING_INTERVAL = 5000; // 5 seconds

export function useBotAccount() {
  const [account, setAccount] = useState<BotAccountState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAccount = useCallback(async () => {
    try {
      const response = await fetch("/api/llm-bot/account");
      if (!response.ok) {
        throw new Error(`Failed to fetch account: ${response.statusText}`);
      }
      const data = await response.json();
      setAccount(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch account");
      console.error("Error fetching bot account:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAccount();
    const interval = setInterval(fetchAccount, POLLING_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchAccount]);

  return { account, loading, error, refetch: fetchAccount };
}

export function useBotAccountHistory(limit: number = 100) {
  const [history, setHistory] = useState<AccountHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    try {
      const response = await fetch(`/api/llm-bot/account/history?limit=${limit}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch history: ${response.statusText}`);
      }
      const data = await response.json();
      setHistory(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch history");
      console.error("Error fetching account history:", err);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    fetchHistory();
    // Refresh history less frequently (every 30 seconds)
    const interval = setInterval(fetchHistory, 30000);
    return () => clearInterval(interval);
  }, [fetchHistory]);

  return { history, loading, error, refetch: fetchHistory };
}
