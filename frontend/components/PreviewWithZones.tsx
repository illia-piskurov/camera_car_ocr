"use client"

import type { ReactNode } from "react"
import { useMemo, useRef, useState } from "react"
import type { BarrierZone, DetectionZone, MotionZone } from "@/lib/types"

type PreviewWithZonesProps = {
    imageSrc: string | null
    zones: DetectionZone[]
    onChangeZones: (zones: DetectionZone[]) => void
    barrierZones?: BarrierZone[]
    activeBarrierZone?: BarrierZone | null
    onChangeActiveBarrierZone?: (zone: BarrierZone) => void
    motionZones?: MotionZone[]
    activeMotionZone?: MotionZone | null
    onChangeActiveMotionZone?: (zone: MotionZone) => void
    headerAction?: ReactNode
}

function zoneLabel(zone: DetectionZone, index: number): string {
    const explicitName = (zone.name ?? "").trim()
    if (explicitName) return explicitName
    const openEntity = (zone.ha_open_entity_id ?? "").trim()
    if (openEntity) return openEntity
    const closeEntity = (zone.ha_close_entity_id ?? "").trim()
    if (closeEntity) return closeEntity
    return `Zone ${index + 1}`
}

type ResizingZone = { zoneIndex: number; corner: "tl" | "tr" | "bl" | "br" }
type ResizingBarrier = { corner: "tl" | "tr" | "bl" | "br" }
type ResizingMotion = { corner: "tl" | "tr" | "bl" | "br" }

function clamp01(value: number): number {
    return Math.max(0, Math.min(1, value))
}

function CornerHandle({
    corner,
    color,
    onPointerDown,
}: {
    corner: "tl" | "tr" | "bl" | "br"
    color: string
    onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => void
}) {
    const posClass = {
        tl: "absolute -top-2 -left-2 cursor-nwse-resize",
        tr: "absolute -top-2 -right-2 cursor-nesw-resize",
        bl: "absolute -bottom-2 -left-2 cursor-nesw-resize",
        br: "absolute -bottom-2 -right-2 cursor-nwse-resize",
    }[corner]
    return (
        <div
            className={`${posClass} size-4 rounded-full border ${color}`}
            onPointerDown={onPointerDown}
        />
    )
}

export function PreviewWithZones({
    imageSrc,
    zones,
    onChangeZones,
    barrierZones,
    activeBarrierZone,
    onChangeActiveBarrierZone,
    motionZones,
    activeMotionZone,
    onChangeActiveMotionZone,
    headerAction,
}: PreviewWithZonesProps) {
    const overlayRef = useRef<HTMLDivElement | null>(null)
    const [resizing, setResizing] = useState<ResizingZone | null>(null)
    const [resizingBarrier, setResizingBarrier] = useState<ResizingBarrier | null>(null)
    const [resizingMotion, setResizingMotion] = useState<ResizingMotion | null>(null)

    const visibleZones = useMemo(
        () => [...zones].sort((a, b) => a.sort_order - b.sort_order),
        [zones],
    )

    function pointToNormalized(clientX: number, clientY: number) {
        const el = overlayRef.current
        if (!el) return null
        const rect = el.getBoundingClientRect()
        if (rect.width <= 0 || rect.height <= 0) return null
        return { x: clamp01((clientX - rect.left) / rect.width), y: clamp01((clientY - rect.top) / rect.height) }
    }

    function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
        const point = pointToNormalized(event.clientX, event.clientY)
        if (!point) return

        if (resizing) {
            const zone = zones[resizing.zoneIndex]
            if (!zone) return
            const z = { ...zone }
            if (resizing.corner === "tl") { z.x_min = Math.min(point.x, zone.x_max - 0.02); z.y_min = Math.min(point.y, zone.y_max - 0.02) }
            else if (resizing.corner === "tr") { z.x_max = Math.max(point.x, zone.x_min + 0.02); z.y_min = Math.min(point.y, zone.y_max - 0.02) }
            else if (resizing.corner === "bl") { z.x_min = Math.min(point.x, zone.x_max - 0.02); z.y_max = Math.max(point.y, zone.y_min + 0.02) }
            else { z.x_max = Math.max(point.x, zone.x_min + 0.02); z.y_max = Math.max(point.y, zone.y_min + 0.02) }
            onChangeZones(zones.map((z2, i) => (i === resizing.zoneIndex ? z : z2)))
        } else if (resizingBarrier && activeBarrierZone && onChangeActiveBarrierZone) {
            const bz = { ...activeBarrierZone }
            if (resizingBarrier.corner === "tl") { bz.x_min = Math.min(point.x, activeBarrierZone.x_max - 0.02); bz.y_min = Math.min(point.y, activeBarrierZone.y_max - 0.02) }
            else if (resizingBarrier.corner === "tr") { bz.x_max = Math.max(point.x, activeBarrierZone.x_min + 0.02); bz.y_min = Math.min(point.y, activeBarrierZone.y_max - 0.02) }
            else if (resizingBarrier.corner === "bl") { bz.x_min = Math.min(point.x, activeBarrierZone.x_max - 0.02); bz.y_max = Math.max(point.y, activeBarrierZone.y_min + 0.02) }
            else { bz.x_max = Math.max(point.x, activeBarrierZone.x_min + 0.02); bz.y_max = Math.max(point.y, activeBarrierZone.y_min + 0.02) }
            onChangeActiveBarrierZone(bz)
        } else if (resizingMotion && activeMotionZone && onChangeActiveMotionZone) {
            const mz = { ...activeMotionZone }
            if (resizingMotion.corner === "tl") { mz.x_min = Math.min(point.x, activeMotionZone.x_max - 0.02); mz.y_min = Math.min(point.y, activeMotionZone.y_max - 0.02) }
            else if (resizingMotion.corner === "tr") { mz.x_max = Math.max(point.x, activeMotionZone.x_min + 0.02); mz.y_min = Math.min(point.y, activeMotionZone.y_max - 0.02) }
            else if (resizingMotion.corner === "bl") { mz.x_min = Math.min(point.x, activeMotionZone.x_max - 0.02); mz.y_max = Math.max(point.y, activeMotionZone.y_min + 0.02) }
            else { mz.x_max = Math.max(point.x, activeMotionZone.x_min + 0.02); mz.y_max = Math.max(point.y, activeMotionZone.y_min + 0.02) }
            onChangeActiveMotionZone(mz)
        }
    }

    function handlePointerUp() {
        setResizing(null)
        setResizingBarrier(null)
        setResizingMotion(null)
    }

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-widest text-slate-400">Live Preview</p>
                {headerAction && <div className="shrink-0">{headerAction}</div>}
            </div>

            <div className="overflow-hidden rounded-lg border border-slate-700/80 bg-slate-900/60">
                {imageSrc ? (
                    <div
                        ref={overlayRef}
                        className="relative cursor-grab active:cursor-grabbing"
                        onPointerMove={handlePointerMove}
                        onPointerUp={handlePointerUp}
                        onPointerLeave={handlePointerUp}
                    >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={imageSrc} alt="Live preview" className="h-auto w-full object-cover" draggable={false} />

                        {/* OCR detection zones (blue/green, editable) */}
                        {visibleZones.map((zone, index) => (
                            <div
                                key={`${zone.id}-${index}`}
                                className={`absolute border-2 ${zone.is_enabled ? "border-emerald-400" : "border-zinc-500"}`}
                                style={{
                                    left: `${zone.x_min * 100}%`, top: `${zone.y_min * 100}%`,
                                    width: `${(zone.x_max - zone.x_min) * 100}%`, height: `${(zone.y_max - zone.y_min) * 100}%`,
                                }}
                            >
                                <span className="absolute -top-6 left-0 rounded bg-black/70 px-2 py-0.5 text-[10px] text-zinc-200">
                                    {zoneLabel(zone, index)}
                                </span>
                                <CornerHandle corner="tl" color="border-blue-300/50 bg-blue-500/70 hover:bg-blue-400" onPointerDown={(e) => { e.stopPropagation(); setResizing({ zoneIndex: index, corner: "tl" }) }} />
                                <CornerHandle corner="tr" color="border-blue-300/50 bg-blue-500/70 hover:bg-blue-400" onPointerDown={(e) => { e.stopPropagation(); setResizing({ zoneIndex: index, corner: "tr" }) }} />
                                <CornerHandle corner="bl" color="border-blue-300/50 bg-blue-500/70 hover:bg-blue-400" onPointerDown={(e) => { e.stopPropagation(); setResizing({ zoneIndex: index, corner: "bl" }) }} />
                                <CornerHandle corner="br" color="border-blue-300/50 bg-blue-500/70 hover:bg-blue-400" onPointerDown={(e) => { e.stopPropagation(); setResizing({ zoneIndex: index, corner: "br" }) }} />
                            </div>
                        ))}

                        {/* Saved barrier check zones (amber dashed, read-only) */}
                        {(barrierZones ?? []).map((bz, idx) => (
                            <div
                                key={`bz-saved-${bz.id}-${idx}`}
                                className="pointer-events-none absolute border-2 border-dashed border-amber-400/40"
                                style={{
                                    left: `${bz.x_min * 100}%`, top: `${bz.y_min * 100}%`,
                                    width: `${(bz.x_max - bz.x_min) * 100}%`, height: `${(bz.y_max - bz.y_min) * 100}%`,
                                }}
                            >
                                <span className="absolute -top-6 left-0 rounded bg-black/70 px-2 py-0.5 text-[10px] text-amber-400/70">
                                    {bz.name?.trim() || (bz.barrier_id != null ? `Barrier ${bz.barrier_id}` : "Barrier zone")}
                                </span>
                            </div>
                        ))}

                        {/* Active barrier check zone (amber solid, editable) */}
                        {activeBarrierZone && (
                            <div
                                className="absolute border-2 border-dashed border-amber-400"
                                style={{
                                    left: `${activeBarrierZone.x_min * 100}%`, top: `${activeBarrierZone.y_min * 100}%`,
                                    width: `${(activeBarrierZone.x_max - activeBarrierZone.x_min) * 100}%`, height: `${(activeBarrierZone.y_max - activeBarrierZone.y_min) * 100}%`,
                                }}
                            >
                                <span className="absolute -top-6 left-0 rounded bg-black/70 px-2 py-0.5 text-[10px] text-amber-300">
                                    {activeBarrierZone.name?.trim() || (activeBarrierZone.barrier_id != null ? `Barrier ${activeBarrierZone.barrier_id}` : "Barrier zone")}
                                </span>
                                <CornerHandle corner="tl" color="border-amber-300/50 bg-amber-500/70 hover:bg-amber-400" onPointerDown={(e) => { e.stopPropagation(); setResizingBarrier({ corner: "tl" }) }} />
                                <CornerHandle corner="tr" color="border-amber-300/50 bg-amber-500/70 hover:bg-amber-400" onPointerDown={(e) => { e.stopPropagation(); setResizingBarrier({ corner: "tr" }) }} />
                                <CornerHandle corner="bl" color="border-amber-300/50 bg-amber-500/70 hover:bg-amber-400" onPointerDown={(e) => { e.stopPropagation(); setResizingBarrier({ corner: "bl" }) }} />
                                <CornerHandle corner="br" color="border-amber-300/50 bg-amber-500/70 hover:bg-amber-400" onPointerDown={(e) => { e.stopPropagation(); setResizingBarrier({ corner: "br" }) }} />
                            </div>
                        )}

                        {/* Saved motion zones (lime dashed, read-only) */}
                        {(motionZones ?? []).filter(mz => mz.id !== activeMotionZone?.id).map((mz, idx) => (
                            <div
                                key={`mz-saved-${mz.id}-${idx}`}
                                className="pointer-events-none absolute border-2 border-dashed border-lime-400/40"
                                style={{
                                    left: `${mz.x_min * 100}%`, top: `${mz.y_min * 100}%`,
                                    width: `${(mz.x_max - mz.x_min) * 100}%`, height: `${(mz.y_max - mz.y_min) * 100}%`,
                                }}
                            >
                                <span className="absolute -top-6 left-0 rounded bg-black/70 px-2 py-0.5 text-[10px] text-lime-400/70">
                                    {mz.name?.trim() || (mz.barrier_id != null ? `Motion ${mz.barrier_id}` : "Motion zone")}
                                </span>
                            </div>
                        ))}

                        {/* Active motion zone (lime solid, editable) */}
                        {activeMotionZone && (
                            <div
                                className="absolute border-2 border-dashed border-lime-400"
                                style={{
                                    left: `${activeMotionZone.x_min * 100}%`, top: `${activeMotionZone.y_min * 100}%`,
                                    width: `${(activeMotionZone.x_max - activeMotionZone.x_min) * 100}%`, height: `${(activeMotionZone.y_max - activeMotionZone.y_min) * 100}%`,
                                }}
                            >
                                <span className="absolute -top-6 left-0 rounded bg-black/70 px-2 py-0.5 text-[10px] text-lime-300">
                                    {activeMotionZone.name?.trim() || (activeMotionZone.barrier_id != null ? `Motion ${activeMotionZone.barrier_id}` : "Motion zone")}
                                </span>
                                <CornerHandle corner="tl" color="border-lime-300/50 bg-lime-500/70 hover:bg-lime-400" onPointerDown={(e) => { e.stopPropagation(); setResizingMotion({ corner: "tl" }) }} />
                                <CornerHandle corner="tr" color="border-lime-300/50 bg-lime-500/70 hover:bg-lime-400" onPointerDown={(e) => { e.stopPropagation(); setResizingMotion({ corner: "tr" }) }} />
                                <CornerHandle corner="bl" color="border-lime-300/50 bg-lime-500/70 hover:bg-lime-400" onPointerDown={(e) => { e.stopPropagation(); setResizingMotion({ corner: "bl" }) }} />
                                <CornerHandle corner="br" color="border-lime-300/50 bg-lime-500/70 hover:bg-lime-400" onPointerDown={(e) => { e.stopPropagation(); setResizingMotion({ corner: "br" }) }} />
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="flex min-h-64 items-center justify-center px-3 text-center text-sm text-slate-400">
                        Frame is not ready yet. Start the recognition pipeline and wait a few seconds.
                    </div>
                )}
            </div>
        </div>
    )
}
