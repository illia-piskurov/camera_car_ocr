import type {
    Barrier,
    BarrierZone,
    CalibrationData,
    Camera,
    CameraCreatePayload,
    CameraGroup,
    CameraUpdatePayload,
    EventsPage,
    ForceSyncResult,
    MotionZone,
    PeerZone,
    PreviewData,
    SaveZonesResponse,
    SystemStatus,
    WhitelistEntry,
    WhitelistPage,
    ZonesResponse,
} from "@/lib/types"

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_API_BASE ?? "http://192.168.100.112:8000"

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

export async function updateCamera(cameraId: number, payload: CameraUpdatePayload): Promise<{ status: string; camera: Camera }> {
    const response = await fetch(`${API_BASE}/api/cameras/${cameraId}`, {
        method: "PUT",
        cache: "no-store",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
    })

    if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Update camera failed: ${errorText}`)
    }

    return (await response.json()) as { status: string; camera: Camera }
}

export async function deleteCamera(cameraId: number): Promise<{ status: string }> {
    const response = await fetch(`${API_BASE}/api/cameras/${cameraId}`, {
        method: "DELETE",
        cache: "no-store",
    })

    if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Delete camera failed: ${errorText}`)
    }

    return (await response.json()) as { status: string }
}

export async function fetchCameraDashboard(cameraId: number, signal?: AbortSignal): Promise<import("@/lib/types").DashboardData> {
    const response = await fetch(`${API_BASE}/api/cameras/${cameraId}/dashboard`, {
        method: "GET",
        cache: "no-store",
        signal,
    })

    if (!response.ok) {
        throw new Error(`Camera dashboard request failed: ${response.status}`)
    }

    return (await response.json()) as import("@/lib/types").DashboardData
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

export async function listCameraGroups(signal?: AbortSignal): Promise<CameraGroup[]> {
    const response = await fetch(`${API_BASE}/api/camera-groups`, { cache: "no-store", signal })
    if (!response.ok) throw new Error(`List groups failed: ${response.status}`)
    const data = (await response.json()) as { groups: CameraGroup[] }
    return data.groups
}

export async function createCameraGroup(payload: { name: string; cross_suppress_sec: number }): Promise<CameraGroup> {
    const response = await fetch(`${API_BASE}/api/camera-groups`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error(`Create group failed: ${response.status}`)
    const data = (await response.json()) as { group: CameraGroup }
    return data.group
}

export async function updateCameraGroup(groupId: number, payload: { name?: string; cross_suppress_sec?: number }): Promise<CameraGroup> {
    const response = await fetch(`${API_BASE}/api/camera-groups/${groupId}`, {
        method: "PUT",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error(`Update group failed: ${response.status}`)
    const data = (await response.json()) as { group: CameraGroup }
    return data.group
}

export async function deleteCameraGroup(groupId: number): Promise<void> {
    const response = await fetch(`${API_BASE}/api/camera-groups/${groupId}`, {
        method: "DELETE",
        cache: "no-store",
    })
    if (!response.ok) throw new Error(`Delete group failed: ${response.status}`)
}

export async function fetchEvents(
    params: {
        cameraId?: number | null
        search?: string
        decision?: string
        offset?: number
        limit?: number
    },
    signal?: AbortSignal,
): Promise<EventsPage> {
    const query = new URLSearchParams()
    if (params.cameraId != null) query.set("camera_id", String(params.cameraId))
    if (params.search) query.set("search", params.search)
    if (params.decision) query.set("decision", params.decision)
    if (params.offset != null) query.set("offset", String(params.offset))
    if (params.limit != null) query.set("limit", String(params.limit))
    const response = await fetch(`${API_BASE}/api/events?${query.toString()}`, { cache: "no-store", signal })
    if (!response.ok) throw new Error(`Events request failed: ${response.status}`)
    return (await response.json()) as EventsPage
}

export async function fetchCameraPeerZones(cameraId: number, signal?: AbortSignal): Promise<PeerZone[]> {
    const response = await fetch(`${API_BASE}/api/cameras/${cameraId}/peer-zones`, { cache: "no-store", signal })
    if (!response.ok) throw new Error(`Peer zones request failed: ${response.status}`)
    const data = (await response.json()) as { peer_zones: PeerZone[] }
    return data.peer_zones
}

export async function listBarriers(signal?: AbortSignal): Promise<Barrier[]> {
    const response = await fetch(`${API_BASE}/api/barriers`, { cache: "no-store", signal })
    if (!response.ok) throw new Error(`List barriers failed: ${response.status}`)
    const data = (await response.json()) as { barriers: Barrier[] }
    return data.barriers
}

export async function createBarrier(payload: { name: string; ha_open_entity_id: string; ha_close_entity_id: string }): Promise<Barrier> {
    const response = await fetch(`${API_BASE}/api/barriers`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error(`Create barrier failed: ${response.status}`)
    const data = (await response.json()) as { barrier: Barrier }
    return data.barrier
}

export async function updateBarrier(barrierId: number, payload: { name?: string; ha_open_entity_id?: string; ha_close_entity_id?: string; state_check_enabled?: boolean; state_threshold?: number }): Promise<Barrier> {
    const response = await fetch(`${API_BASE}/api/barriers/${barrierId}`, {
        method: "PUT",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error(`Update barrier failed: ${response.status}`)
    const data = (await response.json()) as { barrier: Barrier }
    return data.barrier
}

export async function deleteBarrier(barrierId: number): Promise<void> {
    const response = await fetch(`${API_BASE}/api/barriers/${barrierId}`, {
        method: "DELETE",
        cache: "no-store",
    })
    if (!response.ok) throw new Error(`Delete barrier failed: ${response.status}`)
}

export async function saveBarrierCheckZone(
    barrierId: number,
    zone: { camera_id: number | null; name?: string; x_min: number; y_min: number; x_max: number; y_max: number; rotation?: number },
): Promise<BarrierZone | null> {
    const response = await fetch(`${API_BASE}/api/barriers/${barrierId}/check-zone`, {
        method: "PUT",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(zone),
    })
    if (!response.ok) throw new Error(`Save barrier check zone failed: ${response.status}`)
    const data = (await response.json()) as { zone: BarrierZone | null }
    return data.zone
}

export async function deleteBarrierCheckZone(barrierId: number): Promise<void> {
    const response = await fetch(`${API_BASE}/api/barriers/${barrierId}/check-zone`, {
        method: "DELETE",
        cache: "no-store",
    })
    if (!response.ok) throw new Error(`Delete barrier check zone failed: ${response.status}`)
}

export async function getBarrierCalibration(barrierId: number, limit = 60): Promise<CalibrationData> {
    const response = await fetch(`${API_BASE}/api/barriers/${barrierId}/calibration?limit=${limit}`, { cache: "no-store" })
    if (!response.ok) throw new Error(`Get calibration failed: ${response.status}`)
    return (await response.json()) as CalibrationData
}

export async function setCalibrationReference(barrierId: number, eventId: number): Promise<Barrier> {
    const response = await fetch(`${API_BASE}/api/barriers/${barrierId}/calibration/reference`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: eventId }),
    })
    if (!response.ok) {
        const text = await response.text()
        throw new Error(`Set reference failed: ${text}`)
    }
    const data = (await response.json()) as { barrier: Barrier }
    return data.barrier
}

export async function setCalibrationLabel(barrierId: number, eventId: number, label: "open" | "closed" | null): Promise<void> {
    const response = await fetch(`${API_BASE}/api/barriers/${barrierId}/calibration/label`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: eventId, label }),
    })
    if (!response.ok) throw new Error(`Set label failed: ${response.status}`)
}

export async function applyBarrierCalibration(barrierId: number): Promise<{
    threshold: number
    diff_accuracy: number | null
    model_accuracy: number | null
    n_open: number
    n_closed: number
    n_total_labeled: number
}> {
    const response = await fetch(`${API_BASE}/api/barriers/${barrierId}/calibration/apply`, {
        method: "POST",
        cache: "no-store",
    })
    if (!response.ok) {
        const text = await response.text()
        throw new Error(`Apply calibration failed: ${text}`)
    }
    return (await response.json()) as {
        threshold: number
        diff_accuracy: number | null
        model_accuracy: number | null
        n_open: number
        n_closed: number
        n_total_labeled: number
    }
}

export async function listMotionZones(cameraId: number): Promise<MotionZone[]> {
    const response = await fetch(`${API_BASE}/api/cameras/${cameraId}/motion-zones`, { cache: "no-store" })
    if (!response.ok) throw new Error(`List motion zones failed: ${response.status}`)
    const data = (await response.json()) as { motion_zones: MotionZone[] }
    return data.motion_zones
}

export async function createMotionZone(
    cameraId: number,
    payload: { barrier_id: number | null; name?: string; x_min: number; y_min: number; x_max: number; y_max: number },
): Promise<MotionZone> {
    const response = await fetch(`${API_BASE}/api/cameras/${cameraId}/motion-zones`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error(`Create motion zone failed: ${response.status}`)
    const data = (await response.json()) as { zone: MotionZone }
    return data.zone
}

export async function updateMotionZone(
    zoneId: number,
    payload: { barrier_id: number | null; camera_id?: number | null; name?: string; x_min: number; y_min: number; x_max: number; y_max: number },
): Promise<MotionZone> {
    const response = await fetch(`${API_BASE}/api/motion-zones/${zoneId}`, {
        method: "PUT",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error(`Update motion zone failed: ${response.status}`)
    const data = (await response.json()) as { zone: MotionZone }
    return data.zone
}

export async function deleteMotionZone(zoneId: number): Promise<void> {
    const response = await fetch(`${API_BASE}/api/motion-zones/${zoneId}`, {
        method: "DELETE",
        cache: "no-store",
    })
    if (!response.ok) throw new Error(`Delete motion zone failed: ${response.status}`)
}

export async function fetchSystemStatus(signal?: AbortSignal): Promise<SystemStatus> {
    const response = await fetch(`${API_BASE}/api/status`, { cache: "no-store", signal })
    if (!response.ok) throw new Error(`Status request failed: ${response.status}`)
    return (await response.json()) as SystemStatus
}

export async function listWhitelist(params: { search?: string; offset?: number; limit?: number } = {}): Promise<WhitelistPage> {
    const query = new URLSearchParams()
    if (params.search) query.set("search", params.search)
    if (params.offset != null) query.set("offset", String(params.offset))
    if (params.limit != null) query.set("limit", String(params.limit))
    const response = await fetch(`${API_BASE}/api/whitelist?${query.toString()}`, { cache: "no-store" })
    if (!response.ok) throw new Error(`List whitelist failed: ${response.status}`)
    return (await response.json()) as WhitelistPage
}

export async function addWhitelistPlate(plate: string, note: string = ""): Promise<WhitelistEntry> {
    const response = await fetch(`${API_BASE}/api/whitelist`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plate, note }),
    })
    if (!response.ok) {
        const text = await response.text()
        throw new Error(`Add plate failed: ${text}`)
    }
    const data = (await response.json()) as { entry: WhitelistEntry }
    return data.entry
}

export async function updateWhitelistPlate(id: number, payload: { note?: string | null; is_active?: boolean }): Promise<WhitelistEntry> {
    const response = await fetch(`${API_BASE}/api/whitelist/${id}`, {
        method: "PUT",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error(`Update plate failed: ${response.status}`)
    const data = (await response.json()) as { entry: WhitelistEntry }
    return data.entry
}

export async function deleteWhitelistPlate(id: number): Promise<void> {
    const response = await fetch(`${API_BASE}/api/whitelist/${id}`, {
        method: "DELETE",
        cache: "no-store",
    })
    if (!response.ok) throw new Error(`Delete plate failed: ${response.status}`)
}

export async function clearBarrierCalibration(barrierId: number): Promise<void> {
    const response = await fetch(`${API_BASE}/api/barriers/${barrierId}/calibration`, {
        method: "DELETE",
        cache: "no-store",
    })
    if (!response.ok) throw new Error(`Clear calibration failed: ${response.status}`)
}

export async function captureCalibrationFrames(barrierId: number, count: number): Promise<{ captured: { id: number; frame_id: string; occurred_at: string }[] }> {
    const response = await fetch(`${API_BASE}/api/barriers/${barrierId}/calibration/capture?count=${count}`, {
        method: "POST",
        cache: "no-store",
    })
    if (!response.ok) {
        const text = await response.text().catch(() => response.statusText)
        throw new Error(`Capture failed: ${text}`)
    }
    return response.json()
}
