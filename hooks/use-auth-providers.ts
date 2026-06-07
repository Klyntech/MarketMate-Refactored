"use client"

import useSWR from "swr"

interface ProvidersResponse {
  providers: {
    github: boolean
    google: boolean
    email: boolean
  }
}

async function fetchProviders(): Promise<{ github: boolean; google: boolean; email: boolean }> {
  const res = await fetch("/api/auth-providers")
  if (!res.ok) return { github: false, google: false, email: true }
  const data: ProvidersResponse = await res.json()
  return data.providers
}

export function useAuthProviders() {
  const { data } = useSWR("/api/auth-providers", fetchProviders, {
    revalidateOnFocus: false,
    dedupingInterval: 60000,
  })

  return {
    github: data?.github ?? false,
    google: data?.google ?? false,
    email: data?.email ?? true,
    isLoading: !data,
  }
}
