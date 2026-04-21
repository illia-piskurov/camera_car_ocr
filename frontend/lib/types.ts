export type Camera = {
    id: number
    name: string
    snapshot_url: string
    auth_mode: string
    is_active: boolean
    sort_order: number
    created_at: string
    updated_at: string
    has_credentials: boolean
}

export type CameraCreatePayload = {
    name: string
    snapshot_url: string
    username: string
    password: string
    auth_mode: string
}

export type DetectionZone = {
    id: number
    name: string
    x_min: number
    y_min: number
    x_max: number
    y_max: number
    is_enabled: boolean
    sort_order: number
    camera_id?: number | null
    ha_open_entity_id?: string
    ha_close_entity_id?: string
}

export type DashboardEvent = {
    id: number
    occurred_at: string
    frame_id: string
    raw_plate: string
    plate: string
    decision: "open" | "deny" | "observed" | string
    reason_code: string
    detection_confidence: number
    ocr_confidence: number
    vote_confirmations: number | null
    vote_avg_confidence: number | null
    zone_id: number | null
    zone_name: string | null
}

export type DashboardData = {
    generated_at: string
    mode: {
        dry_run_open: boolean
        barrier_action_mode: string
        barrier_close_delay_sec: number
        barrier_live_configured: boolean
        zone1_barrier_configured: boolean
        zone2_barrier_configured: boolean
        zone1_close_delay_sec: number
        zone2_close_delay_sec: number
        ocr_open_threshold: number
        ocr_extend_threshold: number
        two_shot_gap_ms: number
        two_shot_max_pairs: number
        decision_model_version: string
        legacy_config_deprecated: boolean
    }
    sync: {
        last_sync_at: string | null
        sync_age_seconds: number | null
        is_due: boolean
    }
    whitelist: {
        active: number
        inactive: number
    }
    kpi_24h: {
        open: number
        deny: number
        observed: number
        avg_confidence: number
    }
    recent_events: DashboardEvent[]
}

export type ForceSyncResult = {
    status: string
    synced_count: number
    last_sync_at: string | null
}

export type PreviewData = {
    available: boolean
    captured_at: string | null
    has_detections: boolean
    last_plate: string | null
    last_decision: string | null
    zones: DetectionZone[]
    max_zones: number
    image_url: string | null
    version: string | null
}

export type ZonesResponse = {
    max_zones: number
    zones: DetectionZone[]
}

export type SaveZonesResponse = ZonesResponse & {
    status: string
}
