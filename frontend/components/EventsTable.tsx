"use client"

import { useState, useMemo } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { DashboardEvent } from "@/lib/types"

type EventsTableProps = {
    events: DashboardEvent[] | undefined
    loading: boolean
    onEventSelect: (eventId: number) => void
}

const EVENTS_PER_PAGE = 10

function formatTime(value: string | null | undefined) {
    if (!value) return "-"
    return new Date(value).toLocaleString("en-US", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    })
}

function formatPercent(value: number | null | undefined) {
    const v = value ?? 0
    return `${(v * 100).toFixed(0)}%`
}

export function EventsTable({ events, loading, onEventSelect }: EventsTableProps) {
    const [currentPage, setCurrentPage] = useState(1)

    const { paginatedEvents, totalPages } = useMemo(() => {
        if (!events) return { paginatedEvents: [], totalPages: 0 }

        const total = Math.ceil(events.length / EVENTS_PER_PAGE)
        const start = (currentPage - 1) * EVENTS_PER_PAGE
        const end = start + EVENTS_PER_PAGE
        return {
            paginatedEvents: events.slice(start, end),
            totalPages: total,
        }
    }, [events, currentPage])

    const handlePrevPage = () => setCurrentPage((p) => Math.max(1, p - 1))
    const handleNextPage = () => setCurrentPage((p) => Math.min(totalPages, p + 1))

    return (
        <section className="space-y-4">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-4">
                <h3 className="mb-3 text-xs uppercase tracking-widest text-zinc-500">Last Events</h3>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[740px] text-sm">
                        <thead>
                            <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                                <th className="py-2 pr-3">Time</th>
                                <th className="py-2 pr-3">Plate</th>
                                <th className="py-2 pr-3">Zone</th>
                                <th className="py-2 pr-3">Decision</th>
                                <th className="py-2 pr-3">Reason</th>
                                <th className="py-2 pr-3">OCR</th>
                                <th className="py-2">Vote</th>
                            </tr>
                        </thead>
                        <tbody>
                            {paginatedEvents.map((event) => (
                                <tr
                                    key={event.id}
                                    className="cursor-pointer border-b border-zinc-900/70 transition hover:bg-zinc-900/50"
                                    onClick={() => onEventSelect(event.id)}
                                >
                                    <td className="py-2 pr-3 text-zinc-400">{formatTime(event.occurred_at)}</td>
                                    <td className="py-2 pr-3 font-semibold tracking-wide">
                                        {event.plate || event.raw_plate}
                                    </td>
                                    <td className="py-2 pr-3 text-zinc-300">{event.zone_name ?? "all"}</td>
                                    <td className="py-2 pr-3">
                                        <span
                                            className={
                                                event.decision === "open"
                                                    ? "decision-chip-open"
                                                    : event.decision === "deny"
                                                        ? "decision-chip-deny"
                                                        : "decision-chip-observed"
                                            }
                                        >
                                            {event.decision}
                                        </span>
                                    </td>
                                    <td className="py-2 pr-3 text-zinc-300">{event.reason_code}</td>
                                    <td className="py-2 pr-3 text-zinc-300">{formatPercent(event.ocr_confidence)}</td>
                                    <td className="py-2 text-zinc-300">
                                        {event.vote_confirmations ?? "-"}
                                        {event.vote_avg_confidence !== null &&
                                            ` / ${formatPercent(event.vote_avg_confidence)}`}
                                    </td>
                                </tr>
                            ))}
                            {!loading && !paginatedEvents.length && (
                                <tr>
                                    <td colSpan={7} className="py-8 text-center text-zinc-500">
                                        No events yet. Run the pipeline and wait for detections.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Pagination */}
                {totalPages > 0 && (
                    <div className="mt-4 flex items-center justify-between border-t border-zinc-800 pt-4">
                        <Button
                            size="sm"
                            variant="secondary"
                            onClick={handlePrevPage}
                            disabled={currentPage === 1}
                        >
                            <ChevronLeft className="size-4" />
                        </Button>

                        <span className="text-xs text-zinc-500">
                            Page {currentPage} of {totalPages} ({events?.length ?? 0} events)
                        </span>

                        <Button
                            size="sm"
                            variant="secondary"
                            onClick={handleNextPage}
                            disabled={currentPage === totalPages}
                        >
                            <ChevronRight className="size-4" />
                        </Button>
                    </div>
                )}
            </div>
        </section>
    )
}
