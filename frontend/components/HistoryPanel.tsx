"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ChevronDown, ChevronRight, Search, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { fetchEvents } from "@/lib/api"
import type { Camera, DashboardEvent } from "@/lib/types"

const GROUP_WINDOW_MS = 5 * 60 * 1000
const LOAD_BATCH = 200

type EventGroup = {
    plate: string
    events: DashboardEvent[]
    newestAt: Date
    oldestAt: Date
    decision: string
    cameraId: number | null
}

function topDecision(current: string, incoming: string): string {
    if (current === "open" || incoming === "open") return "open"
    if (current === "deny" || incoming === "deny") return "deny"
    return "observed"
}

function groupEvents(events: DashboardEvent[]): EventGroup[] {
    const groups: EventGroup[] = []
    for (const event of events) {
        const t = new Date(event.occurred_at)
        const plate = event.plate || event.raw_plate
        const existing = groups.find(
            (g) => g.plate === plate && g.newestAt.getTime() - t.getTime() < GROUP_WINDOW_MS,
        )
        if (existing) {
            existing.events.push(event)
            existing.oldestAt = t
            existing.decision = topDecision(existing.decision, event.decision)
        } else {
            groups.push({
                plate,
                events: [event],
                newestAt: t,
                oldestAt: t,
                decision: event.decision,
                cameraId: event.camera_id ?? null,
            })
        }
    }
    return groups
}

function formatTime(value: string) {
    return new Date(value).toLocaleString("en-US", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    })
}

function formatShortTime(d: Date) {
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

function formatPercent(v: number | null | undefined) {
    if (v == null) return "—"
    return `${(v * 100).toFixed(0)}%`
}

function DecisionChip({ decision }: { decision: string }) {
    const cls =
        decision === "open"
            ? "decision-chip-open"
            : decision === "deny"
                ? "decision-chip-deny"
                : "decision-chip-observed"
    return <span className={cls}>{decision}</span>
}

type HistoryPanelProps = {
    cameras: Camera[]
    onClose: () => void
    onEventSelect: (eventId: number) => void
}

export function HistoryPanel({ cameras, onClose, onEventSelect }: HistoryPanelProps) {
    const [events, setEvents] = useState<DashboardEvent[]>([])
    const [total, setTotal] = useState(0)
    const [hasMore, setHasMore] = useState(false)
    const [loading, setLoading] = useState(false)
    const [loadingMore, setLoadingMore] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const [cameraFilter, setCameraFilter] = useState<number | null>(null)
    const [decisionFilter, setDecisionFilter] = useState("")
    const [searchInput, setSearchInput] = useState("")
    const [debouncedSearch, setDebouncedSearch] = useState("")

    const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set())

    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    useEffect(() => {
        if (debounceRef.current) clearTimeout(debounceRef.current)
        debounceRef.current = setTimeout(() => setDebouncedSearch(searchInput), 350)
        return () => {
            if (debounceRef.current) clearTimeout(debounceRef.current)
        }
    }, [searchInput])

    const fetchInitial = useCallback(async () => {
        setLoading(true)
        setError(null)
        setEvents([])
        setExpandedKeys(new Set())
        try {
            const result = await fetchEvents({
                cameraId: cameraFilter,
                search: debouncedSearch || undefined,
                decision: decisionFilter || undefined,
                offset: 0,
                limit: LOAD_BATCH,
            })
            setEvents(result.events)
            setTotal(result.total)
            setHasMore(result.has_more)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to load events")
        } finally {
            setLoading(false)
        }
    }, [cameraFilter, decisionFilter, debouncedSearch])

    useEffect(() => {
        void fetchInitial()
    }, [fetchInitial])

    async function loadMore() {
        setLoadingMore(true)
        try {
            const result = await fetchEvents({
                cameraId: cameraFilter,
                search: debouncedSearch || undefined,
                decision: decisionFilter || undefined,
                offset: events.length,
                limit: LOAD_BATCH,
            })
            setEvents((prev) => {
                const existingIds = new Set(prev.map((e) => e.id))
                const fresh = result.events.filter((e) => !existingIds.has(e.id))
                return [...prev, ...fresh]
            })
            setTotal(result.total)
            setHasMore(result.has_more)
        } catch {
            // silently ignore load-more errors
        } finally {
            setLoadingMore(false)
        }
    }

    const groups = useMemo(() => groupEvents(events), [events])

    function toggleGroup(key: string) {
        setExpandedKeys((prev) => {
            const next = new Set(prev)
            if (next.has(key)) next.delete(key)
            else next.add(key)
            return next
        })
    }

    function groupKey(group: EventGroup, index: number) {
        return `${group.plate}-${group.newestAt.getTime()}-${index}`
    }

    useEffect(() => {
        const prev = document.body.style.overflow
        document.body.style.overflow = "hidden"
        return () => {
            document.body.style.overflow = prev
        }
    }, [])

    useEffect(() => {
        function onKey(e: KeyboardEvent) {
            if (e.key === "Escape") onClose()
        }
        document.addEventListener("keydown", onKey)
        return () => document.removeEventListener("keydown", onKey)
    }, [onClose])

    return (
        <div className="fixed inset-0 z-40 flex flex-col bg-slate-900">
            {/* Header */}
            <div className="flex shrink-0 items-center justify-between border-b border-slate-700/80 px-6 py-4">
                <div>
                    <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-200">History</h2>
                    {!loading && (
                        <p className="text-xs text-slate-400">
                            {total} events · {groups.length} groups
                        </p>
                    )}
                </div>
                <button
                    type="button"
                    onClick={onClose}
                    className="rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                    aria-label="Close history"
                >
                    <X className="size-5" />
                </button>
            </div>

            {/* Filter bar */}
            <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-slate-700/60 bg-slate-900/80 px-6 py-3">
                <select
                    value={cameraFilter ?? ""}
                    onChange={(e) => setCameraFilter(e.target.value ? Number(e.target.value) : null)}
                    className="rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-xs text-slate-100 outline-none focus:border-blue-400"
                >
                    <option value="">All cameras</option>
                    {cameras.map((c) => (
                        <option key={c.id} value={c.id}>
                            {c.name}
                        </option>
                    ))}
                </select>

                <select
                    value={decisionFilter}
                    onChange={(e) => setDecisionFilter(e.target.value)}
                    className="rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-xs text-slate-100 outline-none focus:border-blue-400"
                >
                    <option value="">All decisions</option>
                    <option value="open">Open</option>
                    <option value="deny">Deny</option>
                    <option value="observed">Observed</option>
                </select>

                <div className="relative">
                    <Search className="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-slate-500" />
                    <input
                        type="text"
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                        placeholder="Search plate..."
                        className="rounded border border-slate-600 bg-slate-800 py-1.5 pl-7 pr-3 text-xs text-slate-100 outline-none focus:border-blue-400"
                    />
                </div>

                {(cameraFilter !== null || decisionFilter || searchInput) && (
                    <button
                        type="button"
                        onClick={() => {
                            setCameraFilter(null)
                            setDecisionFilter("")
                            setSearchInput("")
                        }}
                        className="text-xs text-slate-400 hover:text-slate-200"
                    >
                        Clear filters
                    </button>
                )}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
                {error && (
                    <p className="mb-4 rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                        {error}
                    </p>
                )}

                {loading ? (
                    <div className="flex items-center justify-center py-16 text-sm text-slate-400">Loading...</div>
                ) : groups.length === 0 ? (
                    <div className="flex items-center justify-center py-16 text-sm text-slate-400">
                        No events found.
                    </div>
                ) : (
                    <div className="space-y-1">
                        {groups.map((group, index) => {
                            const key = groupKey(group, index)
                            const expanded = expandedKeys.has(key)
                            const isSingle = group.events.length === 1
                            const timeLabel = isSingle
                                ? formatShortTime(group.newestAt)
                                : `${formatShortTime(group.oldestAt)} – ${formatShortTime(group.newestAt)}`
                            const cameraName =
                                cameras.length > 1
                                    ? (cameras.find((c) => c.id === group.cameraId)?.name ?? null)
                                    : null

                            return (
                                <div key={key} className="rounded border border-slate-700/60 bg-slate-800/40">
                                    <button
                                        type="button"
                                        className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-slate-800/70"
                                        onClick={() => toggleGroup(key)}
                                    >
                                        {expanded ? (
                                            <ChevronDown className="size-3.5 shrink-0 text-slate-400" />
                                        ) : (
                                            <ChevronRight className="size-3.5 shrink-0 text-slate-400" />
                                        )}
                                        <span className="w-28 shrink-0 font-mono text-sm font-semibold tracking-wide text-slate-100">
                                            {group.plate}
                                        </span>
                                        <span className="text-xs text-slate-400">{timeLabel}</span>
                                        {cameraName && (
                                            <span className="hidden text-xs text-slate-500 sm:inline">{cameraName}</span>
                                        )}
                                        <span className="ml-auto flex shrink-0 items-center gap-2">
                                            {group.events.length > 1 && (
                                                <span className="text-xs text-slate-500">
                                                    {group.events.length} events
                                                </span>
                                            )}
                                            <DecisionChip decision={group.decision} />
                                        </span>
                                    </button>

                                    {expanded && (
                                        <div className="border-t border-slate-700/50">
                                            <div className="overflow-x-auto">
                                                <table className="w-full min-w-[500px] text-xs">
                                                    <thead>
                                                        <tr className="border-b border-slate-700/40 text-left text-[10px] uppercase tracking-wider text-slate-500">
                                                            <th className="px-4 py-1.5">Time</th>
                                                            <th className="px-2 py-1.5">Zone</th>
                                                            <th className="px-2 py-1.5">Decision</th>
                                                            <th className="px-2 py-1.5">Reason</th>
                                                            <th className="px-2 py-1.5 text-right">OCR</th>
                                                            <th className="px-2 py-1.5 text-right">Vote</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {group.events.map((event) => (
                                                            <tr
                                                                key={event.id}
                                                                className="cursor-pointer border-b border-slate-800/60 hover:bg-slate-700/30"
                                                                onClick={() => onEventSelect(event.id)}
                                                            >
                                                                <td className="px-4 py-1.5 text-slate-400">
                                                                    {formatTime(event.occurred_at)}
                                                                </td>
                                                                <td className="px-2 py-1.5 text-slate-300">
                                                                    {event.zone_name ?? "—"}
                                                                </td>
                                                                <td className="px-2 py-1.5">
                                                                    <DecisionChip decision={event.decision} />
                                                                </td>
                                                                <td className="px-2 py-1.5 text-slate-400">
                                                                    {event.reason_code}
                                                                </td>
                                                                <td className="px-2 py-1.5 text-right text-slate-400">
                                                                    {formatPercent(event.ocr_confidence)}
                                                                </td>
                                                                <td className="px-2 py-1.5 text-right text-slate-500">
                                                                    {event.vote_confirmations != null
                                                                        ? `${event.vote_confirmations} / ${formatPercent(event.vote_avg_confidence)}`
                                                                        : "—"}
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )
                        })}
                    </div>
                )}

                {/* Load More / End */}
                {!loading && events.length > 0 && (
                    <div className="mt-6 flex justify-center">
                        {hasMore ? (
                            <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => void loadMore()}
                                disabled={loadingMore}
                                className="border border-slate-600/70 bg-slate-700/80 text-slate-100 hover:bg-slate-600/90"
                            >
                                {loadingMore ? "Loading..." : `Load more — ${events.length} of ${total} loaded`}
                            </Button>
                        ) : (
                            <p className="text-xs text-slate-500">
                                All {total} events loaded · {groups.length} groups
                            </p>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}
