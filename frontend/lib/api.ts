import type { DashboardData, ForceSyncResult, PreviewData } from "@/lib/types"

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

export async function fetchPreview(signal?: AbortSignal): Promise<PreviewData> {
    const response = await fetch(`${API_BASE}/api/preview`, {
        method: "GET",
        cache: "no-store",
        signal,
    })

    if (!response.ok) {
        throw new Error(`Preview request failed: ${response.status}`)
    }

    return (await response.json()) as PreviewData
}

export function toPreviewImageSrc(preview: PreviewData | null): string | null {
    if (!preview?.available || !preview.image_url) {
        return null
    }

    const base = preview.image_url.startsWith("http") ? preview.image_url : `${API_BASE}${preview.image_url}`
    const version = preview.version ?? `${Date.now()}`
    return `${base}?v=${encodeURIComponent(version)}`
}

export function toEventImageSrc(eventId: number): string {
    return `${API_BASE}/api/events/${eventId}/image?v=${Date.now()}`
}
