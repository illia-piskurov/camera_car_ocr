import type { DashboardData, ForceSyncResult } from "@/lib/types"

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_API_BASE ?? "http://127.0.0.1:8000"

export async function fetchDashboard(signal?: AbortSignal): Promise<DashboardData> {
    const response = await fetch(`${API_BASE}/api/dashboard`, {
        method: "GET",
        cache: "no-store",
        signal,
    })

    if (!response.ok) {
        throw new Error(`Dashboard request failed: ${response.status}`)
    }

    return (await response.json()) as DashboardData
}

export async function forceSync(): Promise<ForceSyncResult> {
    const response = await fetch(`${API_BASE}/api/sync/force`, {
        method: "POST",
        cache: "no-store",
    })

    if (!response.ok) {
        throw new Error(`Force sync failed: ${response.status}`)
    }

    return (await response.json()) as ForceSyncResult
}
