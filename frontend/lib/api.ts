import type {
    Camera,
    CameraCreatePayload,
    DashboardData,
    ForceSyncResult,
    PreviewData,
    SaveZonesResponse,
    ZonesResponse,
} from "@/lib/types"

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_API_BASE ?? "http://127.0.0.1:8000"

export async function listCameras(signal?: AbortSignal): Promise<Camera[]> {
    const response = await fetch(`${API_BASE}/api/cameras`, {
        method: "GET",
        cache: "no-store",
        signal,
    })

    if (!response.ok) {
        throw new Error(`List cameras failed: ${response.status}`)
    }

    const data = (await response.json()) as { cameras: Camera[] }
    return data.cameras
}

export async function validateCamera(payload: CameraCreatePayload, signal?: AbortSignal): Promise<{ status: string; available: boolean }> {
    const response = await fetch(`${API_BASE}/api/cameras/validate`, {
        method: "POST",
        cache: "no-store",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        signal,
    })

    if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Camera validation failed: ${errorText}`)
    }

    return (await response.json()) as { status: string; available: boolean }
}

export async function createCamera(payload: CameraCreatePayload): Promise<{ status: string; camera: Camera }> {
    const response = await fetch(`${API_BASE}/api/cameras`, {
        method: "POST",
        cache: "no-store",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
    })

    if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Create camera failed: ${errorText}`)
    }

    return (await response.json()) as { status: string; camera: Camera }
}

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

export async function fetchCameraDashboard(cameraId: number, signal?: AbortSignal): Promise<DashboardData> {
    const response = await fetch(`${API_BASE}/api/cameras/${cameraId}/dashboard`, {
        method: "GET",
        cache: "no-store",
        signal,
    })

    if (!response.ok) {
        throw new Error(`Camera dashboard request failed: ${response.status}`)
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

export async function fetchCameraPreview(cameraId: number, signal?: AbortSignal): Promise<PreviewData> {
    const response = await fetch(`${API_BASE}/api/cameras/${cameraId}/preview`, {
        method: "GET",
        cache: "no-store",
        signal,
    })

    if (!response.ok) {
        throw new Error(`Camera preview request failed: ${response.status}`)
    }

    return (await response.json()) as PreviewData
}

export async function fetchZones(signal?: AbortSignal): Promise<ZonesResponse> {
    const response = await fetch(`${API_BASE}/api/zones`, {
        method: "GET",
        cache: "no-store",
        signal,
    })

    if (!response.ok) {
        throw new Error(`Zones request failed: ${response.status}`)
    }

    return (await response.json()) as ZonesResponse
}

export async function fetchCameraZones(cameraId: number, signal?: AbortSignal): Promise<ZonesResponse> {
    const response = await fetch(`${API_BASE}/api/cameras/${cameraId}/zones`, {
        method: "GET",
        cache: "no-store",
        signal,
    })

    if (!response.ok) {
        throw new Error(`Camera zones request failed: ${response.status}`)
    }

    return (await response.json()) as ZonesResponse
}

export async function saveZones(zones: ZonesResponse["zones"]): Promise<SaveZonesResponse> {
    const response = await fetch(`${API_BASE}/api/zones`, {
        method: "PUT",
        cache: "no-store",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ zones }),
    })

    if (!response.ok) {
        throw new Error(`Save zones failed: ${response.status}`)
    }

    return (await response.json()) as SaveZonesResponse
}

export async function saveCameraZones(cameraId: number, zones: ZonesResponse["zones"]): Promise<SaveZonesResponse> {
    const response = await fetch(`${API_BASE}/api/cameras/${cameraId}/zones`, {
        method: "PUT",
        cache: "no-store",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ zones }),
    })

    if (!response.ok) {
        throw new Error(`Save camera zones failed: ${response.status}`)
    }

    return (await response.json()) as SaveZonesResponse
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
