"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { RefreshCw, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { fetchSystemStatus } from "@/lib/api"
import type { SystemStatus } from "@/lib/types"

function formatAge(sec: number | null | undefined): string {
    if (sec == null) return "—"
    if (sec < 60) return `${Math.round(sec)}s ago`
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`
    return `${Math.floor(sec / 3600)}h ago`
}

function formatTime(iso: string | null | undefined): string {
    if (!iso) return "—"
    return new Date(iso).toLocaleString("uk-UA", {
        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit",
    })
}

function StatusDot({ ok, pulse }: { ok: boolean | null; pulse?: boolean }) {
    const color = ok === null ? "bg-slate-500" : ok ? "bg-emerald-400" : "bg-red-400"
    return (
        <span className={`relative inline-flex size-2.5 rounded-full ${color}`}>
            {pulse && ok && <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-60" />}
        </span>
    )
}

function DecisionChip({ d }: { d: string | null }) {
    if (!d) return <span className="text-slate-600">—</span>
    if (d === "open") return <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-medium text-emerald-300">open</span>
    if (d === "deny") return <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-[10px] font-medium text-red-300">deny</span>
    return <span className="text-slate-400 text-[10px]">{d}</span>
}

function SectionHeader({ title, count }: { title: string; count?: number }) {
    return (
        <div className="flex items-center gap-2 px-6 py-3 border-b border-slate-700/60">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">{title}</h3>
            {count != null && (
                <span className="rounded-full bg-slate-700/60 px-2 py-0.5 text-[10px] text-slate-400">{count}</span>
            )}
        </div>
    )
}

type StatusPanelProps = {
    onClose: () => void
}

export function StatusPanel({ onClose }: StatusPanelProps) {
    const [status, setStatus] = useState<SystemStatus | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
    const abortRef = useRef<AbortController | null>(null)

    const load = useCallback(async () => {
        abortRef.current?.abort()
        const ac = new AbortController()
        abortRef.current = ac
        setLoading(true)
        setError(null)
        try {
            const data = await fetchSystemStatus(ac.signal)
            setStatus(data)
            setLastRefresh(new Date())
        } catch (e) {
            if ((e as Error).name !== "AbortError") {
                setError(e instanceof Error ? e.message : "Failed to load status")
            }
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { void load() }, [load])

    useEffect(() => {
        const prev = document.body.style.overflow
        document.body.style.overflow = "hidden"
        return () => { document.body.style.overflow = prev }
    }, [])

    useEffect(() => {
        function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose() }
        document.addEventListener("keydown", onKey)
        return () => document.removeEventListener("keydown", onKey)
    }, [onClose])

    return (
        <div className="fixed inset-0 z-40 flex flex-col bg-slate-900">
            {/* Header */}
            <div className="flex shrink-0 items-center justify-between border-b border-slate-700/80 px-6 py-4">
                <div>
                    <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-200">System Status</h2>
                    {lastRefresh && (
                        <p className="text-xs text-slate-400">Updated: {lastRefresh.toLocaleTimeString("uk-UA")}</p>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void load()}
                        disabled={loading}
                        className="gap-2 border border-slate-600/70 bg-slate-700/80 text-slate-200 hover:bg-slate-600/90"
                    >
                        <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                    <button type="button" onClick={onClose} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200">
                        <X className="size-5" />
                    </button>
                </div>
            </div>

            {error && (
                <div className="shrink-0 border-b border-red-500/20 bg-red-500/10 px-6 py-2 text-sm text-red-400">{error}</div>
            )}

            <div className="flex-1 overflow-y-auto">
                {!status && !loading && !error && null}

                {status && (
                    <div className="divide-y divide-slate-800/60">

                        {/* Cameras */}
                        <div>
                            <SectionHeader title="Cameras" count={status.cameras.length} />
                            <div className="grid grid-cols-1 gap-0 sm:grid-cols-2 lg:grid-cols-3">
                                {status.cameras.map((cam) => (
                                    <div key={cam.id} className="flex items-center gap-3 px-6 py-3 border-b border-slate-800/40">
                                        <StatusDot ok={cam.is_active && cam.worker_alive} pulse={cam.worker_alive} />
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-medium text-slate-100 truncate">{cam.name}</p>
                                            <p className="text-xs text-slate-500">
                                                {!cam.is_active ? "inactive" : cam.worker_alive ? `worker OK · preview ${formatAge(cam.preview_age_sec)}` : `worker offline · preview ${formatAge(cam.preview_age_sec)}`}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Barriers */}
                        {status.barriers.length > 0 && (
                            <div>
                                <SectionHeader title="Barriers / State Detection" count={status.barriers.length} />
                                <div className="grid grid-cols-1 gap-0 sm:grid-cols-2 lg:grid-cols-3">
                                    {status.barriers.map((b) => {
                                        const stateColor = b.state === "open"
                                            ? "text-emerald-300"
                                            : b.state === "closed"
                                                ? "text-amber-300"
                                                : "text-slate-500"
                                        const fresh = !b.state_stale && b.state != null
                                        return (
                                            <div key={b.id} className="flex items-start gap-3 px-6 py-3 border-b border-slate-800/40">
                                                <StatusDot ok={fresh ? (b.state === "open" ? true : false) : null} pulse={fresh} />
                                                <div className="min-w-0 flex-1">
                                                    <p className="text-sm font-medium text-slate-100 truncate">{b.name}</p>
                                                    <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
                                                        <span className={`font-medium ${stateColor}`}>
                                                            {b.state ?? "unknown"}
                                                        </span>
                                                        {b.state_age_sec != null && (
                                                            <span className={b.state_stale ? "text-red-400" : "text-slate-500"}>
                                                                {formatAge(b.state_age_sec)}{b.state_stale ? " (stale)" : ""}
                                                            </span>
                                                        )}
                                                        {!b.state_check_enabled && <span className="text-slate-600">check disabled</span>}
                                                    </div>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>
                        )}

                        {/* OCR Zones */}
                        {status.ocr_zones.length > 0 && (
                            <div>
                                <SectionHeader title="OCR Detection Zones" count={status.ocr_zones.length} />
                                <table className="w-full text-sm">
                                    <thead className="text-left text-xs uppercase tracking-wider text-slate-500">
                                        <tr>
                                            <th className="px-6 py-2 font-medium">Zone</th>
                                            <th className="px-4 py-2 font-medium">Camera</th>
                                            <th className="px-4 py-2 font-medium">Barrier</th>
                                            <th className="px-4 py-2 font-medium">Last plate</th>
                                            <th className="px-4 py-2 font-medium">Decision</th>
                                            <th className="px-4 py-2 font-medium">Last seen</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {status.ocr_zones.map((z) => (
                                            <tr key={z.id} className={`border-t border-slate-800/60 hover:bg-slate-800/20 ${!z.is_enabled ? "opacity-40" : ""}`}>
                                                <td className="px-6 py-2">
                                                    <div className="flex items-center gap-2">
                                                        <StatusDot ok={z.is_enabled} />
                                                        <span className="font-medium text-slate-100">{z.name}</span>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-2 text-xs text-slate-400">{z.camera_name ?? "—"}</td>
                                                <td className="px-4 py-2 text-xs text-slate-400">{z.barrier_name ?? "—"}</td>
                                                <td className="px-4 py-2 font-mono text-xs text-slate-100">{z.last_plate ?? <span className="text-slate-600">—</span>}</td>
                                                <td className="px-4 py-2"><DecisionChip d={z.last_decision} /></td>
                                                <td className="px-4 py-2 text-xs text-slate-400" title={formatTime(z.last_event_at)}>{formatAge(z.last_event_age_sec)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {/* Motion Zones */}
                        {status.motion_zones.length > 0 && (
                            <div>
                                <SectionHeader title="Motion Zones" count={status.motion_zones.length} />
                                <div className="grid grid-cols-1 gap-0 sm:grid-cols-2 lg:grid-cols-3">
                                    {status.motion_zones.map((z) => (
                                        <div key={z.id} className="px-6 py-3 border-b border-slate-800/40">
                                            <p className="text-sm font-medium text-slate-100 truncate">{z.name || `Motion zone ${z.id}`}</p>
                                            <p className="text-xs text-slate-500">
                                                {[z.camera_name, z.barrier_name ? `→ ${z.barrier_name}` : null].filter(Boolean).join(" · ")}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* System Info */}
                        <div>
                            <SectionHeader title="System" />
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-0">
                                <div className="px-6 py-4 border-b border-slate-800/40 sm:border-r sm:border-b-0">
                                    <p className="text-xs text-slate-500 uppercase tracking-wider">Whitelist</p>
                                    <p className="mt-1 text-2xl font-semibold text-slate-100">{status.whitelist.active}</p>
                                    <p className="text-xs text-slate-500">active plates</p>
                                </div>
                                <div className="px-6 py-4 border-b border-slate-800/40 sm:border-r sm:border-b-0">
                                    <p className="text-xs text-slate-500 uppercase tracking-wider">Last 1C Sync</p>
                                    <p className="mt-1 text-sm font-medium text-slate-100">{formatTime(status.last_sync_at)}</p>
                                    <p className="text-xs text-slate-500">{formatAge(status.sync_age_sec)}</p>
                                </div>
                                <div className="px-6 py-4">
                                    <p className="text-xs text-slate-500 uppercase tracking-wider">Zones configured</p>
                                    <p className="mt-1 text-sm text-slate-300">
                                        {status.ocr_zones.length} OCR · {status.motion_zones.length} motion
                                    </p>
                                </div>
                            </div>
                        </div>

                    </div>
                )}

                {loading && !status && (
                    <div className="flex h-40 items-center justify-center text-sm text-slate-400">Loading…</div>
                )}
            </div>
        </div>
    )
}
