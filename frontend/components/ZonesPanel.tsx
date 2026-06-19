"use client"

import { useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { fetchCameraPeerZones } from "@/lib/api"
import type { DetectionZone, PeerZone } from "@/lib/types"

type ZonesPanelProps = {
    zones: DetectionZone[]
    maxZones: number
    zonesDirty: boolean
    zonesSaving: boolean
    zonesMessage: string | null
    cameraId: number | null
    cameraGroupId: number | null
    onChangeZones: (zones: DetectionZone[]) => void
    onSaveZones: () => void
    onResetZones: () => void
    onUpdateZone: (index: number, updater: (zone: DetectionZone) => DetectionZone) => void
    onRemoveZone: (index: number) => void
}

function inferZoneLabel(zone: DetectionZone, fallbackIndex: number): string {
    const explicit = (zone.name ?? "").trim()
    if (explicit) {
        return explicit
    }

    const openEntity = (zone.ha_open_entity_id ?? "").trim()
    const closeEntity = (zone.ha_close_entity_id ?? "").trim()
    if (openEntity) {
        return openEntity
    }
    if (closeEntity) {
        return closeEntity
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
    cameraGroupId,
    onChangeZones,
    onSaveZones,
    onResetZones,
    onUpdateZone,
    onRemoveZone,
}: ZonesPanelProps) {
    const visibleZones = useMemo(() => {
        return [...zones].sort((a, b) => a.sort_order - b.sort_order)
    }, [zones])

    const [peerZones, setPeerZones] = useState<PeerZone[]>([])

    useEffect(() => {
        if (cameraId === null || cameraGroupId === null) {
            setPeerZones([])
            return
        }
        const controller = new AbortController()
        fetchCameraPeerZones(cameraId, controller.signal)
            .then(setPeerZones)
            .catch(() => setPeerZones([]))
        return () => controller.abort()
    }, [cameraId, cameraGroupId])

    const inGroup = cameraGroupId !== null && peerZones.length > 0

    const messageColor = zonesMessage?.toLowerCase().includes("saved") ? "text-emerald-300" : "text-red-300"

    return (
        <section className="space-y-3 rounded-lg border border-slate-700/80 bg-slate-900/65 p-4">
            <div className="flex items-center justify-between">
                <h3 className="text-xs uppercase tracking-widest text-slate-400">
                    Zones ({zones.length}/{maxZones})
                </h3>
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
                            <div
                                key={`${zone.id}-${index}`}
                                className="space-y-2 rounded border border-slate-700/70 bg-slate-800/55 p-2"
                            >
                                <div className="grid grid-cols-[1fr_auto_auto] items-center gap-2">
                                    <p className="truncate text-xs text-slate-200" title={inferZoneLabel(zone, zoneIndex)}>
                                        {inferZoneLabel(zone, zoneIndex)}
                                    </p>
                                    <button
                                        type="button"
                                        className={`rounded-md px-2 py-1 text-xs font-medium transition ${zone.is_enabled
                                            ? "border border-emerald-500/40 bg-emerald-500/15 text-emerald-200"
                                            : "border border-slate-600/80 bg-slate-700/80 text-slate-300"
                                            }`}
                                        onClick={() =>
                                            onUpdateZone(zoneIndex, (prev) => ({ ...prev, is_enabled: !prev.is_enabled }))
                                        }
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
                                        <span>Open Entity ID</span>
                                        <input
                                            value={zone.ha_open_entity_id ?? ""}
                                            onChange={(event) =>
                                                onUpdateZone(zoneIndex, (prev) => {
                                                    const nextOpen = event.target.value
                                                    const hasName = Boolean((prev.name ?? "").trim())
                                                    return {
                                                        ...prev,
                                                        ha_open_entity_id: nextOpen,
                                                        name: hasName ? prev.name : nextOpen || prev.ha_close_entity_id || prev.name,
                                                    }
                                                })
                                            }
                                            className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                            placeholder="input_button.gate_open"
                                        />
                                    </label>

                                    <label className="space-y-1 text-[11px] text-slate-400">
                                        <span>Close Entity ID</span>
                                        <input
                                            value={zone.ha_close_entity_id ?? ""}
                                            onChange={(event) =>
                                                onUpdateZone(zoneIndex, (prev) => {
                                                    const nextClose = event.target.value
                                                    const hasName = Boolean((prev.name ?? "").trim())
                                                    return {
                                                        ...prev,
                                                        ha_close_entity_id: nextClose,
                                                        name: hasName ? prev.name : prev.ha_open_entity_id || nextClose || prev.name,
                                                    }
                                                })
                                            }
                                            className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                            placeholder="input_button.gate_close"
                                        />
                                    </label>

                                    <label className="space-y-1 text-[11px] text-slate-400">
                                        <span>Label (optional)</span>
                                        <input
                                            value={zone.name ?? ""}
                                            onChange={(event) =>
                                                onUpdateZone(zoneIndex, (prev) => ({ ...prev, name: event.target.value }))
                                            }
                                            onBlur={() =>
                                                onUpdateZone(zoneIndex, (prev) => {
                                                    const currentName = (prev.name ?? "").trim()
                                                    if (currentName) {
                                                        return prev
                                                    }

                                                    const openEntity = (prev.ha_open_entity_id ?? "").trim()
                                                    const closeEntity = (prev.ha_close_entity_id ?? "").trim()
                                                    return {
                                                        ...prev,
                                                        name: openEntity || closeEntity || "",
                                                    }
                                                })
                                            }
                                            className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                            placeholder="Optional display label"
                                        />
                                    </label>

                                    <p className="text-[11px] text-slate-400">
                                        If label is empty, it is auto-filled from entity IDs. Duplicate entity IDs across zones are allowed.
                                    </p>

                                    {/* Cross-camera suppression config — only visible when camera is in a group with peers */}
                                    {inGroup && (
                                        <div className="mt-1 space-y-1.5 rounded border border-slate-600/50 bg-slate-900/40 px-2 py-2">
                                            <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Cross-camera</p>
                                            <label className="flex cursor-pointer items-center gap-2 text-[11px] text-slate-300">
                                                <input
                                                    type="checkbox"
                                                    checked={zone.cross_camera_enabled ?? true}
                                                    onChange={(e) =>
                                                        onUpdateZone(zoneIndex, (prev) => ({ ...prev, cross_camera_enabled: e.target.checked }))
                                                    }
                                                    className="accent-blue-500"
                                                />
                                                Enable suppression for this zone
                                            </label>
                                            {(zone.cross_camera_enabled ?? true) && (
                                                <label className="space-y-1 text-[11px] text-slate-400">
                                                    <span>Suppress when zone opened:</span>
                                                    <select
                                                        value={zone.cross_zone_id ?? ""}
                                                        onChange={(e) =>
                                                            onUpdateZone(zoneIndex, (prev) => ({
                                                                ...prev,
                                                                cross_zone_id: e.target.value ? parseInt(e.target.value) : null,
                                                            }))
                                                        }
                                                        className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                                    >
                                                        <option value="">Any peer camera (group-level)</option>
                                                        {peerZones.map((pz) => (
                                                            <option key={pz.id} value={pz.id}>
                                                                {pz.camera_name} · {pz.name}
                                                            </option>
                                                        ))}
                                                    </select>
                                                </label>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        )
                    })}
                </div>
            ) : (
                <p className="text-xs text-slate-400">No zones configured. Add a zone and set entity IDs.</p>
            )}

            {/* Action Buttons */}
            <div className="flex gap-2 border-t border-slate-700/70 pt-3">
                <Button
                    size="sm"
                    variant="default"
                    onClick={onSaveZones}
                    disabled={!zonesDirty || zonesSaving}
                    className="flex-1 border border-blue-400/30 bg-blue-600/85 text-blue-50 hover:bg-blue-500"
                >
                    {zonesSaving ? "Saving..." : "Save"}
                </Button>
                <Button
                    size="sm"
                    variant="secondary"
                    onClick={onResetZones}
                    disabled={!zonesDirty}
                    className="border border-slate-600/70 bg-slate-700/80 text-slate-100 hover:bg-slate-600/90"
                >
                    Reset
                </Button>
            </div>

            {/* Status Message */}
            {zonesMessage && <p className={`text-xs ${messageColor}`}>{zonesMessage}</p>}
        </section>
    )
}
