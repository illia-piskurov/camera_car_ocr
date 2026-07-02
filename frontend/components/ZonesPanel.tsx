"use client"

import { useMemo } from "react"
import { Button } from "@/components/ui/button"
import type { Barrier, DetectionZone, MotionZone, ZoneGroup } from "@/lib/types"

type ZonesPanelProps = {
    zones: DetectionZone[]
    maxZones: number
    zonesDirty: boolean
    zonesSaving: boolean
    zonesMessage: string | null
    cameraId: number | null
    zoneGroups: ZoneGroup[]
    barriers: Barrier[]
    onChangeZones: (zones: DetectionZone[]) => void
    onSaveZones: () => void
    onResetZones: () => void
    onUpdateZone: (index: number, updater: (zone: DetectionZone) => DetectionZone) => void
    onRemoveZone: (index: number) => void
    onOpenBarriers: () => void
    // Motion zones
    motionZones: MotionZone[]
    activeMotionZone: MotionZone | null
    activeMotionZoneBarrierId: number | null
    activeMotionZoneDirty: boolean
    activeMotionZoneSaving: boolean
    activeMotionZoneMessage: string | null
    onSelectMotionZone: (zone: MotionZone | null) => void
    onSelectMotionBarrier: (barrierId: number | null) => void
    onAddMotionZone: () => void
    onSaveMotionZone: () => void
    onDeleteMotionZone: (zoneId: number) => void
    onResetMotionZone: () => void
}

function inferZoneLabel(zone: DetectionZone, fallbackIndex: number, barriers: Barrier[]): string {
    const explicit = (zone.name ?? "").trim()
    if (explicit) return explicit
    if (zone.barrier_id != null) {
        const barrier = barriers.find((b) => b.id === zone.barrier_id)
        if (barrier) return barrier.name || `Barrier ${barrier.id}`
    }
    return `Zone ${fallbackIndex + 1}`
}

export function ZonesPanel({
    zones,
    maxZones,
    zonesDirty,
    zonesSaving,
    zonesMessage,
    cameraId,
    zoneGroups,
    barriers,
    onChangeZones,
    onSaveZones,
    onResetZones,
    onUpdateZone,
    onRemoveZone,
    onOpenBarriers,
    motionZones,
    activeMotionZone,
    activeMotionZoneBarrierId,
    activeMotionZoneDirty,
    activeMotionZoneSaving,
    activeMotionZoneMessage,
    onSelectMotionZone,
    onSelectMotionBarrier,
    onAddMotionZone,
    onSaveMotionZone,
    onDeleteMotionZone,
    onResetMotionZone,
}: ZonesPanelProps) {
    const visibleZones = useMemo(() => [...zones].sort((a, b) => a.sort_order - b.sort_order), [zones])

    const messageColor = zonesMessage?.toLowerCase().includes("saved") ? "text-emerald-300" : "text-red-300"

    return (
        <section className="space-y-3 rounded-lg border border-slate-700/80 bg-slate-900/65 p-4">
            {/* Header */}
            <div className="flex items-center justify-between gap-2">
                <h3 className="text-xs uppercase tracking-widest text-slate-400">
                    Zones ({zones.length}/{maxZones})
                </h3>
                <div className="flex gap-1.5">
                    <button
                        type="button"
                        onClick={onOpenBarriers}
                        className="rounded border border-slate-600/70 bg-slate-700/80 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-600/90 hover:text-slate-100"
                    >
                        Barriers
                    </button>
                </div>
            </div>

            {/* Add Zone Button */}
            {zones.length < maxZones && (
                <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                        const maxId = zones.length > 0 ? Math.max(...zones.map(z => z.id)) : 0
                        const newZone: DetectionZone = {
                            id: maxId + 1,
                            name: "",
                            ha_open_entity_id: "",
                            ha_close_entity_id: "",
                            x_min: 0.1,
                            y_min: 0.1,
                            x_max: 0.4,
                            y_max: 0.4,
                            is_enabled: true,
                            sort_order: zones.length,
                            cross_camera_enabled: true,
                            cross_zone_id: null,
                        }
                        onChangeZones([...zones, newZone])
                    }}
                    className="w-full border border-slate-600/70 bg-slate-700/85 text-slate-100 hover:bg-slate-600/90"
                >
                    + Add Zone
                </Button>
            )}

            {/* Zones List */}
            {zones.length > 0 ? (
                <div className="space-y-2 border-t border-slate-700/70 pt-3">
                    {visibleZones.map((zone, index) => {
                        const sourceIndex = zones.findIndex((item) => item.id === zone.id)
                        const zoneIndex = sourceIndex >= 0 ? sourceIndex : index
                        return (
                            <div key={`${zone.id}-${index}`} className="space-y-2 rounded border border-slate-700/70 bg-slate-800/55 p-2">
                                <div className="grid grid-cols-[1fr_auto_auto] items-center gap-2">
                                    <p className="truncate text-xs text-slate-200" title={inferZoneLabel(zone, zoneIndex, barriers)}>
                                        {inferZoneLabel(zone, zoneIndex, barriers)}
                                    </p>
                                    <button
                                        type="button"
                                        className={`rounded-md px-2 py-1 text-xs font-medium transition ${zone.is_enabled ? "border border-emerald-500/40 bg-emerald-500/15 text-emerald-200" : "border border-slate-600/80 bg-slate-700/80 text-slate-300"}`}
                                        onClick={() => onUpdateZone(zoneIndex, (prev) => ({ ...prev, is_enabled: !prev.is_enabled }))}
                                    >
                                        {zone.is_enabled ? "ON" : "OFF"}
                                    </button>
                                    <button
                                        type="button"
                                        className="rounded-md border border-red-500/40 bg-red-500/15 px-2 py-1 text-xs text-red-200 hover:bg-red-500/25"
                                        onClick={() => onRemoveZone(zoneIndex)}
                                    >
                                        Delete
                                    </button>
                                </div>

                                <div className="grid gap-2">
                                    <label className="space-y-1 text-[11px] text-slate-400">
                                        <span>Barrier</span>
                                        <select
                                            value={zone.barrier_id ?? ""}
                                            onChange={(event) => onUpdateZone(zoneIndex, (prev) => ({
                                                ...prev,
                                                barrier_id: event.target.value ? parseInt(event.target.value) : null,
                                            }))}
                                            className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                        >
                                            <option value="">— No barrier assigned —</option>
                                            {barriers.map((b) => (
                                                <option key={b.id} value={b.id}>{b.name || `Barrier ${b.id}`}</option>
                                            ))}
                                        </select>
                                    </label>

                                    <label className="space-y-1 text-[11px] text-slate-400">
                                        <span>Label (optional)</span>
                                        <input
                                            value={zone.name ?? ""}
                                            onChange={(event) => onUpdateZone(zoneIndex, (prev) => ({ ...prev, name: event.target.value }))}
                                            className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                            placeholder="Optional display label"
                                        />
                                    </label>

                                    <label className="space-y-1 text-[11px] text-slate-400">
                                        <span>Zone group (suppression)</span>
                                        <select
                                            value={zone.zone_group_id ?? ""}
                                            onChange={(e) => onUpdateZone(zoneIndex, (prev) => ({
                                                ...prev,
                                                zone_group_id: e.target.value ? parseInt(e.target.value) : null,
                                            }))}
                                            className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                        >
                                            <option value="">— No group —</option>
                                            {zoneGroups.map((g) => (
                                                <option key={g.id} value={g.id}>
                                                    {g.name} · {g.suppress_sec}s
                                                </option>
                                            ))}
                                        </select>
                                        {zoneGroups.length === 0 && (
                                            <p className="text-[10px] text-slate-500">No zone groups. Create one via Groups menu.</p>
                                        )}
                                    </label>
                                </div>
                            </div>
                        )
                    })}
                </div>
            ) : (
                <p className="text-xs text-slate-400">No zones configured. Add a zone and assign a barrier.</p>
            )}

            {/* Save/Reset */}
            <div className="flex gap-2 border-t border-slate-700/70 pt-3">
                <Button size="sm" variant="default" onClick={onSaveZones} disabled={!zonesDirty || zonesSaving}
                    className="flex-1 border border-blue-400/30 bg-blue-600/85 text-blue-50 hover:bg-blue-500">
                    {zonesSaving ? "Saving..." : "Save"}
                </Button>
                <Button size="sm" variant="secondary" onClick={onResetZones} disabled={!zonesDirty}
                    className="border border-slate-600/70 bg-slate-700/80 text-slate-100 hover:bg-slate-600/90">
                    Reset
                </Button>
            </div>
            {zonesMessage && <p className={`text-xs ${messageColor}`}>{zonesMessage}</p>}

            {/* Motion Zones */}
            <div className="border-t border-slate-700/70 pt-3 space-y-2">
                <h3 className="text-xs uppercase tracking-widest text-lime-400/80">Motion Zones</h3>
                <p className="text-[11px] text-slate-400">
                    Draw zones covering the passage area. While motion is detected here, the barrier stays open.
                </p>

                {barriers.length === 0 ? (
                    <p className="text-[11px] text-slate-500">No barriers configured yet.</p>
                ) : (
                    <>
                        {/* Existing motion zones list */}
                        {motionZones.length > 0 && (
                            <div className="space-y-1.5">
                                {motionZones.map((mz) => {
                                    const isActive = activeMotionZone?.id === mz.id
                                    const barrier = barriers.find(b => b.id === mz.barrier_id)
                                    return (
                                        <div
                                            key={mz.id}
                                            className={`flex items-center gap-2 rounded border p-2 cursor-pointer transition ${isActive ? "border-lime-500/40 bg-lime-500/10" : "border-slate-700/60 bg-slate-800/50 hover:border-slate-600"}`}
                                            onClick={() => onSelectMotionZone(isActive ? null : mz)}
                                        >
                                            <span className="flex-1 min-w-0 text-[11px] text-slate-200 truncate">
                                                {mz.name?.trim() || "Motion Zone"}
                                                {barrier && <span className="ml-1 text-slate-400">· {barrier.name}</span>}
                                            </span>
                                            {isActive && (
                                                <span className="shrink-0 text-[10px] text-lime-300">editing</span>
                                            )}
                                            <button
                                                type="button"
                                                onClick={(e) => { e.stopPropagation(); void onDeleteMotionZone(mz.id) }}
                                                className="shrink-0 rounded px-1.5 py-0.5 text-[10px] text-red-300 hover:bg-red-500/20"
                                            >
                                                ✕
                                            </button>
                                        </div>
                                    )
                                })}
                            </div>
                        )}

                        {/* Active motion zone editing */}
                        {activeMotionZone && (
                            <div className="space-y-2 rounded border border-lime-500/30 bg-lime-500/5 p-2">
                                <label className="space-y-1 text-[11px] text-slate-400">
                                    <span>Barrier</span>
                                    <select
                                        value={activeMotionZoneBarrierId ?? ""}
                                        onChange={(e) => onSelectMotionBarrier(e.target.value ? parseInt(e.target.value) : null)}
                                        className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-100 outline-none focus:border-lime-400"
                                    >
                                        <option value="">— Select barrier —</option>
                                        {barriers.map((b) => (
                                            <option key={b.id} value={b.id}>{b.name || `Barrier ${b.id}`}</option>
                                        ))}
                                    </select>
                                </label>
                                <p className="text-[11px] text-lime-300">Drag lime handles on the preview to adjust.</p>
                                <div className="flex gap-2">
                                    <Button size="sm" onClick={onSaveMotionZone} disabled={activeMotionZoneSaving}
                                        className="flex-1 border border-lime-500/30 bg-lime-600/80 text-lime-50 hover:bg-lime-500">
                                        {activeMotionZoneSaving ? "Saving..." : "Save"}
                                    </Button>
                                    <Button size="sm" variant="secondary" onClick={onResetMotionZone}
                                        disabled={!activeMotionZoneDirty}
                                        className="border border-slate-600/70 bg-slate-700/80 text-slate-100 hover:bg-slate-600/90">
                                        Reset
                                    </Button>
                                </div>
                            </div>
                        )}

                        {activeMotionZoneMessage && (
                            <p className={`text-xs ${activeMotionZoneMessage.includes("saved") || activeMotionZoneMessage.includes("deleted") ? "text-emerald-300" : "text-red-300"}`}>
                                {activeMotionZoneMessage}
                            </p>
                        )}

                        <Button size="sm" variant="secondary" onClick={onAddMotionZone}
                            className="w-full border border-lime-500/30 bg-lime-500/10 text-lime-200 hover:bg-lime-500/20">
                            + Add Motion Zone
                        </Button>
                    </>
                )}
            </div>
        </section>
    )
}
