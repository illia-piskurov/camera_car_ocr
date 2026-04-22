"use client"

import { useMemo, useRef, useState } from "react"
import type { DetectionZone } from "@/lib/types"

type PreviewWithZonesProps = {
    imageSrc: string | null
    zones: DetectionZone[]
    onChangeZones: (zones: DetectionZone[]) => void
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

type ResizingZone = {
    zoneIndex: number
    corner: "tl" | "tr" | "bl" | "br"
}

function clamp01(value: number): number {
    return Math.max(0, Math.min(1, value))
}

export function PreviewWithZones({
    imageSrc,
    zones,
    onChangeZones,
}: PreviewWithZonesProps) {
    const overlayRef = useRef<HTMLDivElement | null>(null)
    const [resizing, setResizing] = useState<ResizingZone | null>(null)

    const visibleZones = useMemo(() => {
        return [...zones].sort((a, b) => a.sort_order - b.sort_order)
    }, [zones])

    function pointToNormalized(clientX: number, clientY: number) {
        const el = overlayRef.current
        if (!el) return null
        const rect = el.getBoundingClientRect()
        if (rect.width <= 0 || rect.height <= 0) return null
        const x = clamp01((clientX - rect.left) / rect.width)
        const y = clamp01((clientY - rect.top) / rect.height)
        return { x, y }
    }

    function handleCornerPointerDown(
        event: React.PointerEvent<HTMLDivElement>,
        zoneIndex: number,
        corner: "tl" | "tr" | "bl" | "br"
    ) {
        event.stopPropagation()
        setResizing({ zoneIndex, corner })
    }

    function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
        if (!resizing) return
        const point = pointToNormalized(event.clientX, event.clientY)
        if (!point) return
        const zone = zones[resizing.zoneIndex]
        if (!zone) return

        let newZone = { ...zone }
        if (resizing.corner === "tl") {
            newZone.x_min = Math.min(point.x, zone.x_max - 0.02)
            newZone.y_min = Math.min(point.y, zone.y_max - 0.02)
        } else if (resizing.corner === "tr") {
            newZone.x_max = Math.max(point.x, zone.x_min + 0.02)
            newZone.y_min = Math.min(point.y, zone.y_max - 0.02)
        } else if (resizing.corner === "bl") {
            newZone.x_min = Math.min(point.x, zone.x_max - 0.02)
            newZone.y_max = Math.max(point.y, zone.y_min + 0.02)
        } else if (resizing.corner === "br") {
            newZone.x_max = Math.max(point.x, zone.x_min + 0.02)
            newZone.y_max = Math.max(point.y, zone.y_min + 0.02)
        }

        const updated = zones.map((z, i) => (i === resizing.zoneIndex ? newZone : z))
        onChangeZones(updated)
    }

    function handlePointerUp() {
        setResizing(null)
    }

    return (
        <div className="space-y-3">
            <p className="text-xs uppercase tracking-widest text-zinc-500">Live Preview</p>

            {/* Preview Image with Zones Overlay */}
            <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/60">
                {imageSrc ? (
                    <div
                        ref={overlayRef}
                        className="relative cursor-grab active:cursor-grabbing"
                        onPointerMove={handlePointerMove}
                        onPointerUp={handlePointerUp}
                        onPointerLeave={handlePointerUp}
                    >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                            src={imageSrc}
                            alt="Live preview"
                            className="h-auto w-full object-cover"
                            draggable={false}
                        />

                        {/* Render Zones with Resize Handles */}
                        {visibleZones.map((zone, index) => {
                            const left = `${zone.x_min * 100}%`
                            const top = `${zone.y_min * 100}%`
                            const width = `${(zone.x_max - zone.x_min) * 100}%`
                            const height = `${(zone.y_max - zone.y_min) * 100}%`

                            return (
                                <div
                                    key={`${zone.id}-${index}`}
                                    className={`absolute border-2 ${zone.is_enabled ? "border-emerald-400" : "border-zinc-500"
                                        }`}
                                    style={{ left, top, width, height }}
                                >
                                    {/* Zone label */}
                                    <span className="absolute -top-6 left-0 rounded bg-black/70 px-2 py-0.5 text-[10px] text-zinc-200">
                                        {zoneLabel(zone, index)}
                                    </span>

                                    {/* Top-Left Corner Handle */}
                                    <div
                                        className="absolute -top-2 -left-2 size-4 cursor-nwse-resize rounded-full bg-cyan-500/60 hover:bg-cyan-500"
                                        onPointerDown={(e) => handleCornerPointerDown(e, index, "tl")}
                                    />

                                    {/* Top-Right Corner Handle */}
                                    <div
                                        className="absolute -top-2 -right-2 size-4 cursor-nesw-resize rounded-full bg-cyan-500/60 hover:bg-cyan-500"
                                        onPointerDown={(e) => handleCornerPointerDown(e, index, "tr")}
                                    />

                                    {/* Bottom-Left Corner Handle */}
                                    <div
                                        className="absolute -bottom-2 -left-2 size-4 cursor-nesw-resize rounded-full bg-cyan-500/60 hover:bg-cyan-500"
                                        onPointerDown={(e) => handleCornerPointerDown(e, index, "bl")}
                                    />

                                    {/* Bottom-Right Corner Handle */}
                                    <div
                                        className="absolute -bottom-2 -right-2 size-4 cursor-nwse-resize rounded-full bg-cyan-500/60 hover:bg-cyan-500"
                                        onPointerDown={(e) => handleCornerPointerDown(e, index, "br")}
                                    />
                                </div>
                            )
                        })}
                    </div>
                ) : (
                    <div className="flex min-h-64 items-center justify-center px-3 text-center text-sm text-zinc-500">
                        Frame is not ready yet. Start the recognition pipeline and wait a few seconds.
                    </div>
                )}
            </div>
        </div>
    )
}
