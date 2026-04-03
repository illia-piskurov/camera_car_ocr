"use client"

import { useMemo } from "react"
import { Button } from "@/components/ui/button"
import type { DetectionZone } from "@/lib/types"

type ZonesPanelProps = {
    zones: DetectionZone[]
    maxZones: number
    zonesDirty: boolean
    zonesSaving: boolean
    zonesMessage: string | null
    onChangeZones: (zones: DetectionZone[]) => void
    onSaveZones: () => void
    onResetZones: () => void
    onUpdateZone: (index: number, updater: (zone: DetectionZone) => DetectionZone) => void
    onRemoveZone: (index: number) => void
}

export function ZonesPanel({
    zones,
    maxZones,
    zonesDirty,
    zonesSaving,
    zonesMessage,
    onChangeZones,
    onSaveZones,
    onResetZones,
    onUpdateZone,
    onRemoveZone,
}: ZonesPanelProps) {
    const visibleZones = useMemo(() => {
        return [...zones].sort((a, b) => a.sort_order - b.sort_order)
    }, [zones])

    const messageColor = zonesMessage?.toLowerCase().includes("saved") ? "text-emerald-300" : "text-red-300"

    return (
        <section className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-950/70 p-4">
            <div className="flex items-center justify-between">
                <h3 className="text-xs uppercase tracking-widest text-zinc-500">
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
                            name: `Zone ${zones.length + 1}`,
                            x_min: 0.1,
                            y_min: 0.1,
                            x_max: 0.4,
                            y_max: 0.4,
                            is_enabled: true,
                            sort_order: zones.length,
                        }
                        onChangeZones([...zones, newZone])
                    }}
                    className="w-full"
                >
                    + Add Zone
                </Button>
            )}

            {/* Zones List */}
            {zones.length > 0 ? (
                <div className="space-y-2 border-t border-zinc-800 pt-3">
                    {visibleZones.map((zone, index) => (
                        <div
                            key={`${zone.id}-${index}`}
                            className="grid grid-cols-[1fr_auto_auto] items-center gap-2 rounded border border-zinc-800 bg-zinc-900/50 p-2"
                        >
                            <input
                                value={zone.name}
                                onChange={(event) =>
                                    onUpdateZone(index, (prev) => ({ ...prev, name: event.target.value }))
                                }
                                className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 outline-none focus:border-cyan-500"
                                placeholder="Zone name"
                            />
                            <button
                                type="button"
                                className={`rounded px-2 py-1 text-xs font-medium transition ${zone.is_enabled
                                    ? "bg-emerald-500/20 text-emerald-200"
                                    : "bg-zinc-700 text-zinc-400"
                                    }`}
                                onClick={() =>
                                    onUpdateZone(index, (prev) => ({ ...prev, is_enabled: !prev.is_enabled }))
                                }
                            >
                                {zone.is_enabled ? "ON" : "OFF"}
                            </button>
                            <button
                                type="button"
                                className="rounded bg-red-500/20 px-2 py-1 text-xs text-red-200 hover:bg-red-500/30"
                                onClick={() => onRemoveZone(index)}
                            >
                                Delete
                            </button>
                        </div>
                    ))}
                </div>
            ) : (
                <p className="text-xs text-zinc-500">No zones configured</p>
            )}

            {/* Action Buttons */}
            <div className="flex gap-2 border-t border-zinc-800 pt-3">
                <Button
                    size="sm"
                    variant="default"
                    onClick={onSaveZones}
                    disabled={!zonesDirty || zonesSaving}
                    className="flex-1 bg-cyan-600 hover:bg-cyan-700"
                >
                    {zonesSaving ? "Saving..." : "Save"}
                </Button>
                <Button size="sm" variant="secondary" onClick={onResetZones} disabled={!zonesDirty}>
                    Reset
                </Button>
            </div>

            {/* Status Message */}
            {zonesMessage && <p className={`text-xs ${messageColor}`}>{zonesMessage}</p>}
        </section>
    )
}
