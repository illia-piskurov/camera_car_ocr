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
}

export type DashboardData = {
    generated_at: string
    mode: {
        dry_run_open: boolean
        min_confirmations: number
        min_avg_confidence: number
        voting_window_sec: number
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
