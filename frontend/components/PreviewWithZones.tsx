"use client"

import { useMemo, useRef, useState } from "react"
import type { PointerEvent } from "react"

import { Edit2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { DetectionZone } from "@/lib/types"

type DraftRect = {
    x0: number
    y0: number
    x1: number
    y1: number
}

type PreviewWithZonesProps = {
    imageSrc: string | null
    zones: DetectionZone[]
    maxZones: number
    editMode: boolean
    onChangeZones: (zones: DetectionZone[]) => void
    onEditModeToggle: () => void
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

export function PreviewWithZones({
    imageSrc,
    zones,
    maxZones,
    editMode,
    onChangeZones,
    onEditModeToggle,
}: PreviewWithZonesProps) {
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
        if (!editMode || !drawEnabled || !canAddZone) {
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
        const updated = zones
            .filter((_, zoneIndex) => zoneIndex !== index)
            .map((zone, zoneIndex) => ({
                ...zone,
                sort_order: zoneIndex,
                name: zone.name || `Zone ${zoneIndex + 1}`,
            }))
        onChangeZones(updated)
    }

    function clearZones() {
        onChangeZones([])
        setDrawEnabled(false)
        setDraftRect(null)
    }

    return (
        <div className="space-y-3">
            {/* Header with Edit Mode Button */}
            <div className="flex items-center justify-between">
                <p className="text-xs uppercase tracking-widest text-zinc-500">Live Preview</p>
                <Button
                    variant={editMode ? "default" : "secondary"}
                    size="sm"
                    onClick={onEditModeToggle}
                    className={editMode ? "bg-cyan-600 hover:bg-cyan-700" : ""}
                >
                    <Edit2 className="mr-2 size-4" />
                    {editMode ? "Завершить редактирование" : "Редактировать зоны"}
                </Button>
            </div>

            {/* Preview Image with Zones Overlay */}
            <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/60">
                {imageSrc ? (
                    <div
                        ref={overlayRef}
                        className="relative"
                        onPointerDown={handlePointerDown}
                        onPointerMove={handlePointerMove}
                        onPointerUp={handlePointerUp}
                        onPointerLeave={() => {
                            if (isDrawing) {
                                setIsDrawing(false)
                                setDraftRect(null)
                            }
                        }}
                    >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                            src={imageSrc}
                            alt="Live preview"
                            className="h-auto w-full object-cover"
                            draggable={false}
                        />

                        {/* Render Zones */}
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
                                    <span className="absolute -top-6 left-0 rounded bg-black/70 px-2 py-0.5 text-[10px] text-zinc-200">
                                        {zone.name}
                                    </span>
                                </div>
                            )
                        })}

                        {/* Draft Rectangle while drawing */}
                        {editMode && draftRect && (
                            <div
                                className="pointer-events-none absolute border-2 border-cyan-300 bg-cyan-500/10"
                                style={{
                                    left: `${Math.min(draftRect.x0, draftRect.x1) * 100}%`,
                                    top: `${Math.min(draftRect.y0, draftRect.y1) * 100}%`,
                                    width: `${Math.abs(draftRect.x1 - draftRect.x0) * 100}%`,
                                    height: `${Math.abs(draftRect.y1 - draftRect.y0) * 100}%`,
                                }}
                            />
                        )}

                        {/* Help text in edit mode */}
                        {editMode && drawEnabled && (
                            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                                <div className="rounded-lg bg-black/60 px-4 py-2 text-xs text-cyan-200">
                                    Нарисуйте прямоугольник для новой зоны
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="flex min-h-64 items-center justify-center px-3 text-center text-sm text-zinc-500">
                        Кадр еще не готов. Запустите pipeline распознавания и подождите несколько секунд.
                    </div>
                )}
            </div>

            {/* Edit Mode Controls (only visible in edit mode) */}
            {editMode && (
                <div className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
                    <div className="flex flex-wrap gap-2">
                        <Button
                            size="sm"
                            variant={drawEnabled ? "default" : "secondary"}
                            onClick={() => setDrawEnabled(!drawEnabled)}
                            disabled={!canAddZone}
                            className={drawEnabled ? "bg-cyan-600 hover:bg-cyan-700" : ""}
                        >
                            {drawEnabled ? "✓ Режим рисования активен" : "Добавить зону"}
                        </Button>
                        <Button
                            size="sm"
                            variant="secondary"
                            onClick={clearZones}
                            disabled={!zones.length}
                        >
                            Очистить все
                        </Button>
                        <span className="flex items-center text-xs text-zinc-500">
                            {zones.length}/{maxZones} зон
                        </span>
                    </div>

                    {/* Zones List in Edit Mode */}
                    {zones.length > 0 && (
                        <div className="space-y-2 border-t border-zinc-800 pt-3">
                            {visibleZones.map((zone, index) => (
                                <div
                                    key={`${zone.id}-${index}`}
                                    className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-2 rounded border border-zinc-800 bg-zinc-900/50 p-2"
                                >
                                    <input
                                        value={zone.name}
                                        onChange={(event) =>
                                            updateZone(index, (prev) => ({ ...prev, name: event.target.value }))
                                        }
                                        className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 outline-none focus:border-cyan-500"
                                        placeholder="Имя зоны"
                                    />
                                    <button
                                        type="button"
                                        className={`rounded px-2 py-1 text-xs font-medium transition ${zone.is_enabled
                                                ? "bg-emerald-500/20 text-emerald-200"
                                                : "bg-zinc-700 text-zinc-400"
                                            }`}
                                        onClick={() =>
                                            updateZone(index, (prev) => ({ ...prev, is_enabled: !prev.is_enabled }))
                                        }
                                    >
                                        {zone.is_enabled ? "ON" : "OFF"}
                                    </button>
                                    <button
                                        type="button"
                                        className="rounded bg-red-500/20 px-2 py-1 text-xs text-red-200 hover:bg-red-500/30"
                                        onClick={() => removeZone(index)}
                                    >
                                        Удалить
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
