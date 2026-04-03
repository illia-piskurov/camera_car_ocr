"use client"

import { RefreshCw, Zap } from "lucide-react"
import { Button } from "@/components/ui/button"

type ControlRoomHeaderProps = {
    syncAgeSec: number | null
    onRefresh: () => void
    onForceSync: () => void
    refreshing?: boolean
}

function formatSyncAge(seconds: number | null) {
    if (seconds === null) {
        return "no sync yet"
    }

    if (seconds < 60) {
        return `${seconds}s ago`
    }

    const min = Math.floor(seconds / 60)
    if (min < 60) {
        return `${min}m ago`
    }

    const hours = Math.floor(min / 60)
    return `${hours}h ago`
}

export function ControlRoomHeader({
    syncAgeSec,
    onRefresh,
    onForceSync,
    refreshing = false,
}: ControlRoomHeaderProps) {
    const syncStatus = syncAgeSec === null ? "⚠ Pending" : "✓ Connected"

    return (
        <header className="ops-panel flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex-1">
                <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">ALPR Control Room</p>
                <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Barrier Control Room</h1>
            </div>

            <div className="flex items-center gap-3">
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={onRefresh}
                    disabled={refreshing}
                    className="gap-2"
                >
                    <RefreshCw className={`size-4 ${refreshing ? "animate-spin" : ""}`} />
                    Refresh
                </Button>
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={onForceSync}
                    className="gap-2"
                >
                    <Zap className="size-4" />
                    Force Sync
                </Button>
            </div>

            <div className="text-xs text-zinc-500">
                Last sync: {formatSyncAge(syncAgeSec)} | 1C: {syncStatus}
            </div>
        </header>
    )
}
