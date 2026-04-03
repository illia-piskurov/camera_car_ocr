"use client"

import { useMemo, useRef, useState } from "react"
import type { PointerEvent } from "react"

import type { DetectionZone } from "@/lib/types"

type DraftRect = {
    x0: number
    y0: number
    x1: number
    y1: number
}

type ZoneEditorProps = {
    imageSrc: string | null
    zones: DetectionZone[]
    maxZones: number
    onChangeZones: (zones: DetectionZone[]) => void
}

function clamp01(value: number): number {
    return Math.max(0, Math.min(1, value))
}

function normalizeRect(rect: DraftRect) {
    const xMin = Math.min(rect.x0, rect.x1)
    const yMin = Math.min(rect.y0, rect.y1)
    const xMax = Math.max(rect.x0, rect.x1)
    const yMax = Math.max(rect.y0, rect.y1)

    const minSpan = 0.02
    return {
        x_min: xMin,
        y_min: yMin,
        x_max: xMax < xMin + minSpan ? Math.min(1, xMin + minSpan) : xMax,
        y_max: yMax < yMin + minSpan ? Math.min(1, yMin + minSpan) : yMax,
    }
}

export function ZoneEditor({ imageSrc, zones, maxZones, onChangeZones }: ZoneEditorProps) {
    const overlayRef = useRef<HTMLDivElement | null>(null)

    const [isDrawing, setIsDrawing] = useState(false)
    const [drawEnabled, setDrawEnabled] = useState(false)
    const [draftRect, setDraftRect] = useState<DraftRect | null>(null)

    const canAddZone = zones.length < maxZones

    const visibleZones = useMemo(() => {
        return [...zones].sort((a, b) => a.sort_order - b.sort_order)
    }, [zones])

    function pointToNormalized(clientX: number, clientY: number) {
        const el = overlayRef.current
        if (!el) {
            return null
        }

        const rect = el.getBoundingClientRect()
        if (rect.width <= 0 || rect.height <= 0) {
            return null
        }

        const x = clamp01((clientX - rect.left) / rect.width)
        const y = clamp01((clientY - rect.top) / rect.height)
        return { x, y }
    }

    function handlePointerDown(event: PointerEvent<HTMLDivElement>) {
        if (!drawEnabled || !canAddZone) {
            return
        }

        const point = pointToNormalized(event.clientX, event.clientY)
        if (!point) {
            return
        }

        setIsDrawing(true)
        setDraftRect({ x0: point.x, y0: point.y, x1: point.x, y1: point.y })
    }

    function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
        if (!isDrawing || !draftRect) {
            return
        }

        const point = pointToNormalized(event.clientX, event.clientY)
        if (!point) {
            return
        }

        setDraftRect((prev) => (prev ? { ...prev, x1: point.x, y1: point.y } : prev))
    }

    function handlePointerUp() {
        if (!isDrawing || !draftRect) {
            return
        }

        const rect = normalizeRect(draftRect)
        const nextZone: DetectionZone = {
            id: Date.now(),
            name: `Zone ${zones.length + 1}`,
            x_min: rect.x_min,
            y_min: rect.y_min,
            x_max: rect.x_max,
            y_max: rect.y_max,
            is_enabled: true,
            sort_order: zones.length,
        }

        onChangeZones([...zones, nextZone])
        setIsDrawing(false)
        setDraftRect(null)
        setDrawEnabled(false)
    }

    function updateZone(index: number, updater: (zone: DetectionZone) => DetectionZone) {
        const updated = zones.map((zone, zoneIndex) => (zoneIndex === index ? updater(zone) : zone))
        onChangeZones(updated)
    }

    function removeZone(index: number) {
        const updated = zones.filter((_, zoneIndex) => zoneIndex !== index).map((zone, zoneIndex) => ({
            ...zone,
            sort_order: zoneIndex,
            name: zone.name || `Zone ${zoneIndex + 1}`,
        }))
        onChangeZones(updated)
    }

    function clearZones() {
        onChangeZones([])
    }

    return (
        <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
                <button
                    type="button"
                    className="rounded-md border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() => setDrawEnabled(true)}
                    disabled={!canAddZone}
                >
                    Add Zone
                </button>
                <button
                    type="button"
                    className="rounded-md border border-zinc-700 px-3 py-1 text-xs text-zinc-300"
                    onClick={clearZones}
                    disabled={!zones.length}
                >
                    Clear
                </button>
                <p className="self-center text-xs text-zinc-500">
                    {zones.length}/{maxZones} zones
                </p>
            </div>

            <div className="overflow-hidden rounded-md border border-zinc-800 bg-zinc-900/60">
                {imageSrc ? (
                    <div
                        ref={overlayRef}
                        className="relative"
                        onPointerDown={handlePointerDown}
                        onPointerMove={handlePointerMove}
                        onPointerUp={handlePointerUp}
                    >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={imageSrc} alt="Live preview" className="h-auto w-full object-cover" draggable={false} />

                        {visibleZones.map((zone, index) => {
                            const left = `${zone.x_min * 100}%`
                            const top = `${zone.y_min * 100}%`
                            const width = `${(zone.x_max - zone.x_min) * 100}%`
                            const height = `${(zone.y_max - zone.y_min) * 100}%`

                            return (
                                <div
                                    key={`${zone.id}-${index}`}
                                    className={`absolute border-2 ${zone.is_enabled ? "border-emerald-400" : "border-zinc-500"}`}
                                    style={{ left, top, width, height }}
                                >
                                    <span className="absolute -top-6 left-0 rounded bg-black/70 px-2 py-0.5 text-[10px] text-zinc-200">
                                        {zone.name}
                                    </span>
                                </div>
                            )
                        })}

                        {draftRect && (
                            <div
                                className="pointer-events-none absolute border-2 border-cyan-300"
                                style={{
                                    left: `${Math.min(draftRect.x0, draftRect.x1) * 100}%`,
                                    top: `${Math.min(draftRect.y0, draftRect.y1) * 100}%`,
                                    width: `${Math.abs(draftRect.x1 - draftRect.x0) * 100}%`,
                                    height: `${Math.abs(draftRect.y1 - draftRect.y0) * 100}%`,
                                }}
                            />
                        )}
                    </div>
                ) : (
                    <div className="flex min-h-44 items-center justify-center px-3 text-center text-sm text-zinc-500">
                        Frame is not ready yet. Wait for the live preview.
                    </div>
                )}
            </div>

            <div className="space-y-2">
                {zones.map((zone, index) => (
                    <div key={`${zone.id}-${index}`} className="grid grid-cols-[1fr_auto_auto] items-center gap-2 rounded border border-zinc-800 p-2">
                        <input
                            value={zone.name}
                            onChange={(event) => updateZone(index, (prev) => ({ ...prev, name: event.target.value }))}
                            className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 outline-none"
                        />
                        <button
                            type="button"
                            className={`rounded px-2 py-1 text-xs ${zone.is_enabled ? "bg-emerald-500/20 text-emerald-200" : "bg-zinc-700 text-zinc-300"}`}
                            onClick={() => updateZone(index, (prev) => ({ ...prev, is_enabled: !prev.is_enabled }))}
                        >
                            {zone.is_enabled ? "ON" : "OFF"}
                        </button>
                        <button
                            type="button"
                            className="rounded bg-red-500/20 px-2 py-1 text-xs text-red-200"
                            onClick={() => removeZone(index)}
                        >
                            Delete
                        </button>
                    </div>
                ))}
            </div>
        </div>
    )
}
