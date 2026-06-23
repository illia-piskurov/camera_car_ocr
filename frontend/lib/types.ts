export type CameraGroup = {
    id: number
    name: string
    cross_suppress_sec: number
    created_at: string
    updated_at: string
}

export type Camera = {
    id: number
    name: string
    snapshot_url: string
    auth_mode: string
    is_active: boolean
    sort_order: number
    group_id: number | null
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
    is_active?: boolean
    sort_order?: number | null
    group_id?: number | null
}

export type CameraUpdatePayload = {
    name?: string
    snapshot_url?: string
    username?: string
    password?: string
    auth_mode?: string
    is_active?: boolean
    sort_order?: number | null
    group_id?: number | null
}

export type Barrier = {
    id: number
    name: string
    ha_open_entity_id: string
    ha_close_entity_id: string
    state_check_enabled: boolean
    state_threshold: number
    state_reference_event_id: number | null
    has_reference: boolean
    has_model: boolean
    created_at: string
    updated_at: string
}

export type CalibrationSample = {
    event_id: number
    occurred_at: string | null
    image_url: string
    crop_b64: string | null
    diff_score: number | null
    model_prob: number | null
    predicted_label: "open" | "closed" | null
    user_label: "open" | "closed" | null
}

export type CalibrationData = {
    barrier_id: number
    reference_event_id: number | null
    has_reference: boolean
    has_model: boolean
    threshold: number
    samples: CalibrationSample[]
    error?: string
}

export type DetectionZone = {
    id: number
    name?: string
    x_min: number
    y_min: number
    x_max: number
    y_max: number
    is_enabled: boolean
    sort_order: number
    camera_id?: number | null
    barrier_id?: number | null
    ha_open_entity_id?: string
    ha_close_entity_id?: string
    cross_camera_enabled: boolean
    cross_zone_id: number | null
    zone_type?: string
}

export type BarrierZone = {
    id: number
    barrier_id: number | null
    camera_id?: number | null
    name?: string
    x_min: number
    y_min: number
    x_max: number
    y_max: number
    zone_type: "barrier_check"
}

export type PeerZone = {
    id: number
    camera_id: number
    camera_name: string
    name: string
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
    camera_id: number | null
}

export type DashboardData = {
    generated_at: string
    mode: {
        dry_run_open: boolean
        barrier_action_mode: string
        barrier_close_delay_sec: number
        barrier_live_configured: boolean
        ocr_open_threshold: number
        ocr_extend_threshold: number
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

export type EventsPage = {
    events: DashboardEvent[]
    total: number
    offset: number
    limit: number
    has_more: boolean
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
    barriers: Barrier[]
    barrier_zones: BarrierZone[]
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
