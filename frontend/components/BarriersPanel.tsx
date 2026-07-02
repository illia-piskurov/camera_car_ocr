"use client"

import { useEffect, useState } from "react"
import { Plus, Trash2, X, Check, PencilLine } from "lucide-react"
import { Button } from "@/components/ui/button"
import { listBarriers, createBarrier, updateBarrier, deleteBarrier } from "@/lib/api"
import type { Barrier } from "@/lib/types"

interface BarriersPanelProps {
    onClose: () => void
    onBarriersChanged?: () => void
}

export function BarriersPanel({ onClose, onBarriersChanged }: BarriersPanelProps) {
    const [barriers, setBarriers] = useState<Barrier[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const [editingId, setEditingId] = useState<number | null>(null)
    const [editName, setEditName] = useState("")
    const [editOpen, setEditOpen] = useState("")
    const [editClose, setEditClose] = useState("")
    const [editOpenSensor, setEditOpenSensor] = useState("")
    const [editCloseSensor, setEditCloseSensor] = useState("")
    const [editStateEnabled, setEditStateEnabled] = useState(false)
    const [editBusy, setEditBusy] = useState(false)

    const [creatingNew, setCreatingNew] = useState(false)
    const [newName, setNewName] = useState("")
    const [newOpen, setNewOpen] = useState("")
    const [newClose, setNewClose] = useState("")
    const [createBusy, setCreateBusy] = useState(false)

    const [deletingId, setDeletingId] = useState<number | null>(null)
    const [deleteBusy, setDeleteBusy] = useState(false)

    useEffect(() => {
        let alive = true
        listBarriers()
            .then((list) => {
                if (alive) {
                    setBarriers(list)
                    setLoading(false)
                }
            })
            .catch((err) => {
                if (alive) {
                    setError(err instanceof Error ? err.message : "Failed to load barriers")
                    setLoading(false)
                }
            })
        return () => { alive = false }
    }, [])

    function startEdit(barrier: Barrier) {
        setEditingId(barrier.id)
        setEditName(barrier.name)
        setEditOpen(barrier.ha_open_entity_id)
        setEditClose(barrier.ha_close_entity_id)
        setEditOpenSensor(barrier.ha_open_sensor_id)
        setEditCloseSensor(barrier.ha_close_sensor_id)
        setEditStateEnabled(barrier.state_check_enabled)
    }

    async function saveEdit() {
        if (editingId === null) return
        setEditBusy(true)
        try {
            const updated = await updateBarrier(editingId, {
                name: editName,
                ha_open_entity_id: editOpen,
                ha_close_entity_id: editClose,
                ha_open_sensor_id: editOpenSensor,
                ha_close_sensor_id: editCloseSensor,
                state_check_enabled: editStateEnabled,
            })
            setBarriers((prev) => prev.map((b) => (b.id === editingId ? updated : b)))
            setEditingId(null)
            onBarriersChanged?.()
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save barrier")
        } finally {
            setEditBusy(false)
        }
    }

    async function handleCreate() {
        setCreateBusy(true)
        try {
            const created = await createBarrier({
                name: newName.trim() || "New Barrier",
                ha_open_entity_id: newOpen.trim(),
                ha_close_entity_id: newClose.trim(),
            })
            setBarriers((prev) => [...prev, created])
            setCreatingNew(false)
            setNewName("")
            setNewOpen("")
            setNewClose("")
            onBarriersChanged?.()
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to create barrier")
        } finally {
            setCreateBusy(false)
        }
    }

    async function handleDelete(barrierId: number) {
        setDeleteBusy(true)
        try {
            await deleteBarrier(barrierId)
            setBarriers((prev) => prev.filter((b) => b.id !== barrierId))
            setDeletingId(null)
            onBarriersChanged?.()
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to delete barrier")
        } finally {
            setDeleteBusy(false)
        }
    }

    return (
        <>
        <div className="fixed inset-0 z-50 flex items-start justify-end bg-black/50 p-4">
            <div className="flex h-full w-full max-w-md flex-col rounded-xl border border-slate-700/90 bg-slate-900 shadow-2xl">
                {/* Header */}
                <div className="flex shrink-0 items-center justify-between border-b border-slate-700/70 px-4 py-3">
                    <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-300">Barriers</h2>
                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded p-1 text-slate-400 hover:bg-slate-700/60 hover:text-slate-100"
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Body */}
                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
                    {loading && <p className="text-sm text-slate-400">Loading...</p>}
                    {error && <p className="text-sm text-red-300">{error}</p>}

                    {barriers.map((barrier) => (
                        <div
                            key={barrier.id}
                            className="rounded-lg border border-slate-700/70 bg-slate-800/60 p-3 space-y-2"
                        >
                            {editingId === barrier.id ? (
                                <div className="space-y-2">
                                    <label className="space-y-1 text-[11px] text-slate-400">
                                        <span>Name</span>
                                        <input
                                            value={editName}
                                            onChange={(e) => setEditName(e.target.value)}
                                            className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                            placeholder="Gate 1"
                                        />
                                    </label>
                                    <label className="space-y-1 text-[11px] text-slate-400">
                                        <span>Open Entity ID</span>
                                        <input
                                            value={editOpen}
                                            onChange={(e) => setEditOpen(e.target.value)}
                                            className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                            placeholder="input_button.gate_open"
                                        />
                                    </label>
                                    <label className="space-y-1 text-[11px] text-slate-400">
                                        <span>Close Entity ID</span>
                                        <input
                                            value={editClose}
                                            onChange={(e) => setEditClose(e.target.value)}
                                            className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                            placeholder="input_button.gate_close"
                                        />
                                    </label>
                                    <div className="space-y-1.5 rounded border border-slate-700/60 bg-slate-900/50 px-2 py-2">
                                        <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">State Detection</p>
                                        <label className="flex cursor-pointer items-center gap-2 text-[11px] text-slate-300">
                                            <input
                                                type="checkbox"
                                                checked={editStateEnabled}
                                                onChange={(e) => setEditStateEnabled(e.target.checked)}
                                                className="accent-amber-500"
                                            />
                                            Check state before opening (skip if already open)
                                        </label>
                                        {editStateEnabled && (
                                            <div className="space-y-1.5 pt-0.5">
                                                <label className="space-y-1 text-[11px] text-slate-400">
                                                    <span>Open sensor entity ID</span>
                                                    <input
                                                        value={editOpenSensor}
                                                        onChange={(e) => setEditOpenSensor(e.target.value)}
                                                        className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-amber-400"
                                                        placeholder="binary_sensor.gate_open"
                                                    />
                                                </label>
                                                <label className="space-y-1 text-[11px] text-slate-400">
                                                    <span>Close sensor entity ID</span>
                                                    <input
                                                        value={editCloseSensor}
                                                        onChange={(e) => setEditCloseSensor(e.target.value)}
                                                        className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-amber-400"
                                                        placeholder="binary_sensor.gate_closed"
                                                    />
                                                </label>
                                                <p className="text-[10px] text-slate-500">
                                                    ON = barrier is in that state. At least one sensor required.
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex gap-2 pt-1">
                                        <Button
                                            size="sm"
                                            onClick={() => void saveEdit()}
                                            disabled={editBusy}
                                            className="flex-1 border border-blue-400/30 bg-blue-600/85 text-blue-50 hover:bg-blue-500"
                                        >
                                            <Check size={13} className="mr-1" />
                                            {editBusy ? "Saving..." : "Save"}
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="secondary"
                                            onClick={() => setEditingId(null)}
                                            disabled={editBusy}
                                            className="border border-slate-600/70 bg-slate-700/80 text-slate-100 hover:bg-slate-600/90"
                                        >
                                            Cancel
                                        </Button>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-1.5">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium text-slate-100 truncate">
                                                {barrier.name || <span className="text-slate-500 italic">Unnamed</span>}
                                            </p>
                                            <p className="text-[11px] text-slate-400 truncate mt-0.5">
                                                Open: {barrier.ha_open_entity_id || <span className="text-slate-600">—</span>}
                                            </p>
                                            <p className="text-[11px] text-slate-400 truncate">
                                                Close: {barrier.ha_close_entity_id || <span className="text-slate-600">—</span>}
                                            </p>
                                            {barrier.state_check_enabled && (
                                                <div className="mt-1 space-y-0.5">
                                                    <span className="inline-block rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-300">
                                                        State check ON
                                                    </span>
                                                    {barrier.ha_open_sensor_id && (
                                                        <p className="text-[10px] text-slate-500 truncate">
                                                            Open sensor: {barrier.ha_open_sensor_id}
                                                        </p>
                                                    )}
                                                    {barrier.ha_close_sensor_id && (
                                                        <p className="text-[10px] text-slate-500 truncate">
                                                            Close sensor: {barrier.ha_close_sensor_id}
                                                        </p>
                                                    )}
                                                    {!barrier.ha_open_sensor_id && !barrier.ha_close_sensor_id && (
                                                        <p className="text-[10px] text-red-400/70">no sensors configured</p>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                        <div className="flex shrink-0 gap-1">
                                            <button
                                                type="button"
                                                onClick={() => startEdit(barrier)}
                                                className="rounded p-1.5 text-slate-400 hover:bg-slate-700/60 hover:text-slate-100"
                                                title="Edit"
                                            >
                                                <PencilLine size={14} />
                                            </button>
                                        {deletingId === barrier.id ? (
                                            <div className="flex gap-1">
                                                <button
                                                    type="button"
                                                    onClick={() => void handleDelete(barrier.id)}
                                                    disabled={deleteBusy}
                                                    className="rounded px-2 py-1 text-[11px] bg-red-600/80 text-red-50 hover:bg-red-500"
                                                >
                                                    {deleteBusy ? "…" : "Delete"}
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setDeletingId(null)}
                                                    className="rounded p-1.5 text-slate-400 hover:bg-slate-700/60"
                                                >
                                                    <X size={13} />
                                                </button>
                                            </div>
                                        ) : (
                                            <button
                                                type="button"
                                                onClick={() => setDeletingId(barrier.id)}
                                                className="rounded p-1.5 text-slate-400 hover:bg-red-500/20 hover:text-red-300"
                                                title="Delete"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}

                    {/* New barrier form */}
                    {creatingNew ? (
                        <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-3 space-y-2">
                            <p className="text-[11px] font-medium uppercase tracking-wider text-blue-300">New Barrier</p>
                            <label className="space-y-1 text-[11px] text-slate-400">
                                <span>Name</span>
                                <input
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                    placeholder="Gate 1"
                                    autoFocus
                                />
                            </label>
                            <label className="space-y-1 text-[11px] text-slate-400">
                                <span>Open Entity ID</span>
                                <input
                                    value={newOpen}
                                    onChange={(e) => setNewOpen(e.target.value)}
                                    className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                    placeholder="input_button.gate_open"
                                />
                            </label>
                            <label className="space-y-1 text-[11px] text-slate-400">
                                <span>Close Entity ID</span>
                                <input
                                    value={newClose}
                                    onChange={(e) => setNewClose(e.target.value)}
                                    className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100 outline-none focus:border-blue-400"
                                    placeholder="input_button.gate_close"
                                />
                            </label>
                            <div className="flex gap-2 pt-1">
                                <Button
                                    size="sm"
                                    onClick={() => void handleCreate()}
                                    disabled={createBusy}
                                    className="flex-1 border border-blue-400/30 bg-blue-600/85 text-blue-50 hover:bg-blue-500"
                                >
                                    {createBusy ? "Creating..." : "Create"}
                                </Button>
                                <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => setCreatingNew(false)}
                                    className="border border-slate-600/70 bg-slate-700/80 text-slate-100 hover:bg-slate-600/90"
                                >
                                    Cancel
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <button
                            type="button"
                            onClick={() => setCreatingNew(true)}
                            className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-slate-600/60 py-3 text-sm text-slate-400 hover:border-slate-500 hover:text-slate-300 transition"
                        >
                            <Plus size={16} />
                            Add Barrier
                        </button>
                    )}

                    {!loading && barriers.length === 0 && !creatingNew && (
                        <p className="text-center text-xs text-slate-500 py-2">
                            No barriers configured. Each barrier maps a physical gate to its Home Assistant entity IDs.
                        </p>
                    )}
                </div>

                {/* Footer hint */}
                <div className="shrink-0 border-t border-slate-700/70 px-4 py-3">
                    <p className="text-[11px] text-slate-500">
                        Assign barriers to detection zones in the Zones panel. Configure check zones on the camera preview.
                    </p>
                </div>
            </div>
        </div>

    </>
    )
}
