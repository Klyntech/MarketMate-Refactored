"use client"

import useSWR from "swr"
import { api, type Signal, type PerformanceStats, type TradesResponse, type PerformanceResponse, type HealthResponse } from "@/lib/api"

// Extended types for auth awareness
interface TradesResponseWithMeta extends TradesResponse {
  auth_required?: boolean
  backend_down?: boolean
}

interface PerformanceResponseWithMeta {
  "7_day": PerformanceStats | null
  "30_day": PerformanceStats | null
  auth_required?: boolean
  backend_down?: boolean
}

// SWR fetcher functions
const fetchTrades = async (): Promise<TradesResponseWithMeta> => {
  return api.getTrades()
}

const fetchPerformance = async (): Promise<PerformanceResponseWithMeta> => {
  return api.getPerformance()
}

const fetchHealth = async (): Promise<HealthResponse> => {
  return api.health()
}

/**
 * Hook to fetch open trades/signals
 */
export function useTrades(options?: { refreshInterval?: number }) {
  const { data, error, isLoading, mutate } = useSWR<TradesResponseWithMeta>(
    "/api/trades",
    fetchTrades,
    {
      refreshInterval: options?.refreshInterval ?? 30000,
      revalidateOnFocus: true,
      dedupingInterval: 5000,
      // Don't retry on 503 (backend down) — wait for next refresh
      onErrorRetry: (err, _key, _config, revalidate, { retryCount }) => {
        if (retryCount >= 2) return
        setTimeout(() => revalidate({ retryCount }), 10000)
      },
    }
  )

  const isAuthRequired = data?.auth_required === true
  const isBackendDown = data?.backend_down === true || !!error

  return {
    trades: data?.trades ?? [],
    count: data?.count ?? 0,
    isLoading,
    isAuthRequired,
    isBackendDown,
    isError: isBackendDown && !isAuthRequired,
    error,
    refresh: mutate,
  }
}

/**
 * Hook to fetch performance stats
 */
export function usePerformance(options?: { refreshInterval?: number }) {
  const { data, error, isLoading, mutate } = useSWR<PerformanceResponseWithMeta>(
    "/api/performance",
    fetchPerformance,
    {
      refreshInterval: options?.refreshInterval ?? 60000,
      revalidateOnFocus: true,
      dedupingInterval: 10000,
      onErrorRetry: (err, _key, _config, revalidate, { retryCount }) => {
        if (retryCount >= 2) return
        setTimeout(() => revalidate({ retryCount }), 10000)
      },
    }
  )

  const isAuthRequired = data?.auth_required === true
  const isBackendDown = data?.backend_down === true || !!error

  return {
    stats7Day: data?.["7_day"] ?? null,
    stats30Day: data?.["30_day"] ?? null,
    isLoading,
    isAuthRequired,
    isBackendDown,
    isError: isBackendDown && !isAuthRequired,
    error,
    refresh: mutate,
  }
}

/**
 * Hook to check API health
 */
export function useHealth() {
  const { data, error, isLoading } = useSWR<HealthResponse>(
    "/api/health",
    fetchHealth,
    {
      refreshInterval: 60000,
      revalidateOnFocus: false,
    }
  )

  return {
    status: data?.status ?? "unknown",
    isHealthy: data?.status === "ok" && !data?.backend_down,
    isLoading,
    isError: !!error,
    isBackendDown: data?.backend_down === true,
  }
}

// Re-export types for convenience
export type { Signal, PerformanceStats, TradesResponse, PerformanceResponse }
