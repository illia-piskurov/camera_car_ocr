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
type RotatingBarrier = {}  // Used as marker that we're rotating a barrier zone

function clamp01(value: number): number {
    return Math.max(0, Math.min(1, value))
}

function normalizeAngle(angle: number): number {
    // Normalize to [0, 360)
    angle = angle % 360
    if (angle < 0) angle += 360
    return angle
}

// Calculate the 4 corners of a rotated rectangle in normalized coordinates
function getRotatedRectCorners(
  xMin: number, yMin: number, xMax: number, yMax: number,
  rotationDeg: number
): {x: number, y: number}[] {
  const cx = (xMin + xMax) / 2
  const cy = (yMin + yMax) / 2
  const halfW = (xMax - xMin) / 2
  const halfH = (yMax - yMin) / 2
  const rad = (rotationDeg * Math.PI) / 180

  // Corners before rotation (relative to center)
  const corners = [
    {x: -halfW, y: -halfH},  // top-left
    {x: halfW, y: -halfH},   // top-right
    {x: halfW, y: halfH},    // bottom-right
    {x: -halfW, y: halfH}    // bottom-left
  ]

  // Rotate and translate back to absolute coordinates
  const cos = Math.cos(rad)
  const sin = Math.sin(rad)

  return corners.map(c => ({
    x: cx + c.x * cos - c.y * sin,
    y: cy + c.x * sin + c.y * cos
  }))
}

// Calculate rotation handle position (above the top edge)
function getRotationHandlePosition(
  xMin: number, yMin: number, xMax: number, yMax: number,
  rotationDeg: number
): {x: number, y: number} {
  const cx = (xMin + xMax) / 2
  const cy = (yMin + yMax) / 2
  const halfW = (xMax - xMin) / 2
  const halfH = (yMax - yMin) / 2
  const rad = (rotationDeg * Math.PI) / 180

  // Point at the center of the top edge, rotated
  const topX = 0
  const topY = -halfH - 0.03  // 3% above the top edge

  const cos = Math.cos(rad)
  const sin = Math.sin(rad)

  return {
    x: cx + topX * cos - topY * sin,
    y: cy + topX * sin + topY * cos
  }
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

function RotationHandle({
    x,
    y,
    color,
    onPointerDown,
}: {
    x: number
    y: number
    color: string
    onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => void
}) {
    return (
        <div
            className="absolute size-4 rounded-full border cursor-grab active:cursor-grabbing"
            style={{
                left: `${x * 100}%`,
                top: `${y * 100}%`,
                transform: "translate(-50%, -50%)",
                color,
            }}
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
    const [rotatingBarrier, setRotatingBarrier] = useState<RotatingBarrier | null>(null)

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
        } else if (rotatingBarrier && activeBarrierZone && onChangeActiveBarrierZone) {
            // Calculate angle from zone center to mouse position
            const cx = (activeBarrierZone.x_min + activeBarrierZone.x_max) / 2
            const cy = (activeBarrierZone.y_min + activeBarrierZone.y_max) / 2
            const dx = point.x - cx
            const dy = point.y - cy
            // Adjust: -90 degrees because angle 0 is at right (3 o'clock), but we want 0 to be up
            const angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90
            onChangeActiveBarrierZone({
                ...activeBarrierZone,
                rotation: normalizeAngle(angle)
            })
        }
    }

    function handlePointerUp() {
        setResizing(null)
        setResizingBarrier(null)
        setResizingMotion(null)
        setRotatingBarrier(null)
    }

    // Convert corners to SVG polygon points string
    function cornersToPoints(corners: {x: number, y: number}[]): string {
        return corners.map(c => `${(c.x * 100).toFixed(2)}% ${(c.y * 100).toFixed(2)}%`).join(" ")
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

                        {/* OCR detection zones (blue/green, editable) - axis-aligned only */}
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

                        {/* Saved barrier check zones (amber dashed, read-only) - with rotation support */}
                        {(barrierZones ?? []).map((bz, idx) => {
                            const rotation = bz.rotation ?? 0
                            const isRotated = Math.abs(rotation % 360) > 0.1

                            if (isRotated) {
                                // Rotated zone - render as SVG polygon
                                const corners = getRotatedRectCorners(bz.x_min, bz.y_min, bz.x_max, bz.y_max, rotation)
                                return (
                                    <svg key={`bz-saved-${bz.id}-${idx}`} className="pointer-events-none absolute inset-0 h-full w-full">
                                        <polygon
                                            points={cornersToPoints(corners)}
                                            fill="none"
                                            stroke="rgba(251, 191, 36, 0.4)"
                                            strokeWidth="2"
                                            strokeDasharray="5,5"
                                        />
                                    </svg>
                                )
                            }

                            // Axis-aligned zone - render as div
                            return (
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
                            )
                        })}

                        {/* Active barrier check zone (amber solid, editable) - with rotation support */}
                        {activeBarrierZone && (
                            <>
                                {(() => {
                                    const rotation = activeBarrierZone.rotation ?? 0
                                    const isRotated = Math.abs(rotation % 360) > 0.1

                                    if (isRotated) {
                                        // Rotated zone - render as SVG polygon
                                        const corners = getRotatedRectCorners(
                                            activeBarrierZone.x_min, activeBarrierZone.y_min,
                                            activeBarrierZone.x_max, activeBarrierZone.y_max,
                                            rotation
                                        )
                                        const handlePos = getRotationHandlePosition(
                                            activeBarrierZone.x_min, activeBarrierZone.y_min,
                                            activeBarrierZone.x_max, activeBarrierZone.y_max,
                                            rotation
                                        )

                                        return (
                                            <>
                                                <svg className="pointer-events-none absolute inset-0 h-full w-full">
                                                    <polygon
                                                        points={cornersToPoints(corners)}
                                                        fill="none"
                                                        stroke="rgb(251, 191, 36)"
                                                        strokeWidth="2"
                                                        strokeDasharray="5,5"
                                                    />
                                                    {/* Line from zone center to rotation handle */}
                                                    <line
                                                        x1={`${((activeBarrierZone.x_min + activeBarrierZone.x_max) / 2) * 100}%`}
                                                        y1={`${((activeBarrierZone.y_min + activeBarrierZone.y_max) / 2) * 100}%`}
                                                        x2={`${handlePos.x * 100}%`}
                                                        y2={`${handlePos.y * 100}%`}
                                                        stroke="rgb(251, 191, 36)"
                                                        strokeWidth="1"
                                                        strokeDasharray="3,3"
                                                    />
                                                </svg>
                                                {/* Rotation handle */}
                                                <RotationHandle
                                                    x={handlePos.x}
                                                    y={handlePos.y}
                                                    color="border-amber-300/50 bg-amber-500/70 hover:bg-amber-400"
                                                    onPointerDown={(e) => { e.stopPropagation(); setRotatingBarrier({}) }}
                                                />
                                                {/* Corner handles - we can't easily use simple positioning with rotation, so we render them based on corners */}
                                                {corners.map((corner, cIdx) => (
                                                    <div
                                                        key={`corner-${cIdx}`}
                                                        className="absolute size-4 rounded-full border border-amber-300/50 bg-amber-500/70 hover:bg-amber-400"
                                                        style={{
                                                            left: `${corner.x * 100}%`,
                                                            top: `${corner.y * 100}%`,
                                                            transform: "translate(-50%, -50%)",
                                                        }}
                                                        onPointerDown={(e) => {
                                                            e.stopPropagation()
                                                            const cornerTypes: ("tl" | "tr" | "bl" | "br")[] = ["tl", "tr", "br", "bl"]
                                                            setResizingBarrier({ corner: cornerTypes[cIdx] })
                                                        }}
                                                    />
                                                ))}
                                            </>
                                        )
                                    }

                                    // Axis-aligned zone - render as div
                                    return (
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
                                    )
                                })()}
                            </>
                        )}

                        {/* Saved motion zones (lime dashed, read-only) - axis-aligned only */}
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

                        {/* Active motion zone (lime solid, editable) - axis-aligned only */}
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