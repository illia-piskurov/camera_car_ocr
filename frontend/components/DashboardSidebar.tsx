"use client"

import { useMemo } from "react"
import { AlertCircle, CheckCircle2, RefreshCw, Siren } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { DashboardData, PreviewData, DetectionZone } from "@/lib/types"

type DashboardSidebarProps = {
    data: DashboardData | null
    preview: PreviewData | null
    zones: DetectionZone[]
    maxZones: number
    zonesDirty: boolean
    zonesSaving: boolean
    zonesMessage: string | null
    onSaveZones: () => void
    onResetZones: () => void
    onUpdateZone: (index: number, updater: (zone: DetectionZone) => DetectionZone) => void
    onRemoveZone: (index: number) => void
    syncAgeSec: number | null
}

function zoneLabel(zone: DetectionZone, index: number): string {
    const explicitName = (zone.name ?? "").trim()
    if (explicitName) {
        return explicitName
    }

    const openEntity = (zone.ha_open_entity_id ?? "").trim()
    if (openEntity) {
        return openEntity
    }

    const closeEntity = (zone.ha_close_entity_id ?? "").trim()
    if (closeEntity) {
        return closeEntity
    }

    return `Zone ${index + 1}`
}

function formatTime(value: string | null | undefined) {
    if (!value) {
        return "-"
    }
    return new Date(value).toLocaleString("en-US")
}

function formatPercent(value: number | null | undefined) {
    const nextValue = value ?? 0
    return `${(nextValue * 100).toFixed(1)}%`
}

function formatSyncAge(seconds: number | null) {
    if (seconds === null) {
        return "No data"
    }

    if (seconds < 60) {
        return `${seconds}s ago`
    }

    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) {
        return `${minutes}m ago`
    }

    const hours = Math.floor(minutes / 60)
    return `${hours}h ago`
}

export function DashboardSidebar({
    data,
    preview,
    zones,
    maxZones,
    zonesDirty,
    zonesSaving,
    zonesMessage,
    onSaveZones,
    onResetZones,
    onUpdateZone,
    onRemoveZone,
    syncAgeSec,
}: DashboardSidebarProps) {
    const visibleZones = useMemo(() => [...zones].sort((a, b) => a.sort_order - b.sort_order), [zones])

    const messageIsError = zonesMessage?.toLowerCase().includes("error") ?? false

    return (
        <aside className="space-y-4">
            <section className="space-y-3">
                <h3 className="text-xs uppercase tracking-widest text-zinc-500">Operations</h3>

                <article className="ops-card">
                    <p className="ops-label">Opening mode</p>
                    <div className="mt-2 flex items-center gap-2">
                        {data?.mode.dry_run_open ? (
                            <>
                                <AlertCircle className="size-5 text-amber-400" />
                                <span className="text-lg font-semibold text-amber-300">DRY-RUN</span>
                            </>
                        ) : (
                            <>
                                <CheckCircle2 className="size-5 text-emerald-400" />
                                <span className="text-lg font-semibold text-emerald-300">ACTIVE</span>
                            </>
                        )}
                    </div>
                    <p className="mt-2 text-xs text-zinc-400">
                        Model: {data?.mode.decision_model_version ?? "-"}
                    </p>
                </article>

                <article className="ops-card">
                    <p className="ops-label">Decisions in 24h</p>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-semibold text-emerald-300">{data?.kpi_24h.open ?? 0}</span>
                        <span className="text-sm text-zinc-400">open</span>
                    </div>
                    <p className="mt-1 text-xs text-zinc-400">deny: {data?.kpi_24h.deny ?? 0}</p>
                </article>

                <article className="ops-card">
                    <p className="ops-label">Average confidence</p>
                    <p className="mt-2 text-2xl font-semibold">{formatPercent(data?.kpi_24h.avg_confidence)}</p>
                    <p className="mt-1 text-xs text-zinc-400">latest confirmed decisions</p>
                </article>
            </section>

            <section className="space-y-3 border-t border-zinc-800 pt-4">
                <h3 className="text-xs uppercase tracking-widest text-zinc-500">Integrations</h3>

                <div className="space-y-2 text-sm">
                    <div className="ops-kv">
                        <span>1C sync</span>
                        <span className={data?.sync.is_due ? "text-amber-300" : "text-emerald-300"}>
                            {data?.sync.is_due ? "due" : "up to date"}
                        </span>
                    </div>
                    <div className="ops-kv">
                        <span>Last sync</span>
                        <span>{formatTime(data?.sync.last_sync_at)}</span>
                    </div>
                    <div className="ops-kv">
                        <span>Sync age</span>
                        <span>{formatSyncAge(syncAgeSec)}</span>
                    </div>
                </div>

                <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
                    <p className="text-xs uppercase tracking-widest text-zinc-500">New frame</p>
                    <div className="mt-2 space-y-1 text-xs text-zinc-400">
                        <p>Time: {formatTime(preview?.captured_at)}</p>
                        <p>Detections: {preview?.has_detections ? "✓ yes" : "no"}</p>
                        <p>Plate: {preview?.last_plate ?? "-"}</p>
                        <p>Decision: {preview?.last_decision ?? "-"}</p>
                    </div>
                </div>
            </section>

            <section className="space-y-3 border-t border-zinc-800 pt-4">
                <h3 className="text-xs uppercase tracking-widest text-zinc-500">
                    Zones ({zones.length}/{maxZones})
                </h3>

                {zones.length > 0 ? (
                    <div className="max-h-48 space-y-2 overflow-y-auto">
                        {visibleZones.map((zone, index) => (
                            <div
                                key={`${zone.id}-${index}`}
                                className="flex items-center gap-2 rounded border border-zinc-800 bg-zinc-900/50 px-2 py-1.5"
                            >
                                <button
                                    type="button"
                                    className={`flex h-6 w-6 flex-shrink-0 rounded border transition ${zone.is_enabled
                                        ? "border-emerald-500/30 bg-emerald-500/20 text-emerald-300"
                                        : "border-zinc-700 bg-zinc-700/30 text-zinc-500"
                                        }`}
                                    onClick={() => onUpdateZone(index, (prev) => ({ ...prev, is_enabled: !prev.is_enabled }))}
                                    title={zone.is_enabled ? "Disable zone" : "Enable zone"}
                                >
                                    {zone.is_enabled ? "✓" : ""}
                                </button>

                                <span className="flex-1 truncate text-xs font-medium text-zinc-300">{zoneLabel(zone, index)}</span>

                                <button
                                    type="button"
                                    className="flex-shrink-0 text-sm text-red-400 transition hover:text-red-300"
                                    onClick={() => onRemoveZone(index)}
                                    title="Delete zone"
                                >
                                    ✕
                                </button>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-xs italic text-zinc-500">No zones configured</p>
                )}

                <div className="flex flex-col gap-2 border-t border-zinc-800 pt-3">
                    <Button onClick={onSaveZones} disabled={!zonesDirty || zonesSaving} className="w-full">
                        {zonesSaving ? (
                            <>
                                <RefreshCw className="mr-2 size-4 animate-spin" />
                                Saving...
                            </>
                        ) : (
                            "Save zones"
                        )}
                    </Button>
                    <Button variant="secondary" onClick={onResetZones} disabled={zonesSaving} className="w-full">
                        Reset
                    </Button>
                    {zonesMessage && (
                        <p
                            className={`rounded px-2 py-1 text-center text-xs ${messageIsError ? "bg-red-500/10 text-red-300" : "bg-emerald-500/10 text-emerald-300"
                                }`}
                        >
                            {zonesMessage}
                        </p>
                    )}
                </div>
            </section>

            <section className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
                <p className="text-xs uppercase tracking-widest text-zinc-500">Safety</p>
                <p className="mt-2 text-sm text-zinc-300">
                    The system is configured as fail-closed. If the outcome is uncertain, the gate does not open.
                </p>
                <div className="mt-3 flex items-center gap-2 text-amber-300">
                    <Siren className="size-4" />
                    <span className="text-xs">Preference: false deny &gt; false open</span>
                </div>
            </section>
        </aside>
    )
}
