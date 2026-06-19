"use client"

import { useEffect, useState } from "react"
import { PencilLine, Plus, Trash2, X, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { listCameraGroups, createCameraGroup, updateCameraGroup, deleteCameraGroup } from "@/lib/api"
import type { CameraGroup } from "@/lib/types"

interface CameraGroupsPanelProps {
    onClose: () => void
}

function formatSuppressTime(sec: number): string {
    if (sec < 60) return `${sec}s`
    const min = Math.floor(sec / 60)
    return `${min}m`
}

export function CameraGroupsPanel({ onClose }: CameraGroupsPanelProps) {
    const [groups, setGroups] = useState<CameraGroup[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const [editingId, setEditingId] = useState<number | null>(null)
    const [editName, setEditName] = useState("")
    const [editSuppress, setEditSuppress] = useState("")
    const [editBusy, setEditBusy] = useState(false)

    const [deletingId, setDeletingId] = useState<number | null>(null)
    const [deleteBusy, setDeleteBusy] = useState(false)

    const [showCreate, setShowCreate] = useState(false)
    const [createName, setCreateName] = useState("")
    const [createSuppress, setCreateSuppress] = useState("120")
    const [createBusy, setCreateBusy] = useState(false)

    async function load() {
        setLoading(true)
        setError(null)
        try {
            setGroups(await listCameraGroups())
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to load groups")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { void load() }, [])

    function startEdit(group: CameraGroup) {
        setEditingId(group.id)
        setEditName(group.name)
        setEditSuppress(String(group.cross_suppress_sec))
        setDeletingId(null)
    }

    function cancelEdit() {
        setEditingId(null)
    }

    async function saveEdit() {
        if (!editingId) return
        setEditBusy(true)
        try {
            await updateCameraGroup(editingId, {
                name: editName.trim(),
                cross_suppress_sec: parseInt(editSuppress) || 120,
            })
            setEditingId(null)
            await load()
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to update group")
        } finally {
            setEditBusy(false)
        }
    }

    async function confirmDelete(groupId: number) {
        setDeleteBusy(true)
        try {
            await deleteCameraGroup(groupId)
            setDeletingId(null)
            await load()
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to delete group")
        } finally {
            setDeleteBusy(false)
        }
    }

    async function handleCreate() {
        if (!createName.trim()) return
        setCreateBusy(true)
        setError(null)
        try {
            await createCameraGroup({
                name: createName.trim(),
                cross_suppress_sec: parseInt(createSuppress) || 120,
            })
            setCreateName("")
            setCreateSuppress("120")
            setShowCreate(false)
            await load()
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to create group")
        } finally {
            setCreateBusy(false)
        }
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-900 shadow-2xl">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-slate-700/80 px-6 py-4">
                    <div>
                        <h2 className="text-lg font-semibold text-slate-100">Camera Groups</h2>
                        <p className="mt-0.5 text-xs text-slate-400">
                            Cameras in the same group suppress duplicate opens across each other.
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-700/60 hover:text-slate-200"
                    >
                        <X className="size-5" />
                    </button>
                </div>

                <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
                    {error && (
                        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                            {error}
                        </div>
                    )}

                    {loading ? (
                        <p className="text-sm text-slate-400">Loading...</p>
                    ) : groups.length === 0 && !showCreate ? (
                        <p className="text-sm italic text-slate-500">No groups yet. Create one to link cameras.</p>
                    ) : (
                        <ul className="space-y-2">
                            {groups.map((group) => (
                                <li
                                    key={group.id}
                                    className="rounded-lg border border-slate-700/70 bg-slate-800/60 px-4 py-3"
                                >
                                    {editingId === group.id ? (
                                        <div className="space-y-2">
                                            <input
                                                autoFocus
                                                type="text"
                                                value={editName}
                                                onChange={(e) => setEditName(e.target.value)}
                                                placeholder="Group name"
                                                className="w-full rounded border border-slate-600 bg-slate-700 px-2 py-1.5 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none"
                                            />
                                            <div className="flex items-center gap-2">
                                                <label className="text-xs text-slate-400 whitespace-nowrap">Suppress window (sec):</label>
                                                <input
                                                    type="number"
                                                    min="0"
                                                    value={editSuppress}
                                                    onChange={(e) => setEditSuppress(e.target.value)}
                                                    className="w-24 rounded border border-slate-600 bg-slate-700 px-2 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
                                                />
                                            </div>
                                            <div className="flex gap-2">
                                                <Button size="sm" onClick={() => void saveEdit()} disabled={editBusy || !editName.trim()}>
                                                    <Check className="mr-1 size-3.5" />
                                                    {editBusy ? "Saving..." : "Save"}
                                                </Button>
                                                <Button size="sm" variant="secondary" onClick={cancelEdit}>
                                                    Cancel
                                                </Button>
                                            </div>
                                        </div>
                                    ) : deletingId === group.id ? (
                                        <div>
                                            <p className="text-sm text-slate-200">
                                                Delete <span className="font-semibold">{group.name}</span>?
                                                Cameras in this group will be unassigned.
                                            </p>
                                            <div className="mt-2 flex gap-2">
                                                <Button
                                                    size="sm"
                                                    variant="destructive"
                                                    onClick={() => void confirmDelete(group.id)}
                                                    disabled={deleteBusy}
                                                >
                                                    {deleteBusy ? "Deleting..." : "Delete"}
                                                </Button>
                                                <Button size="sm" variant="secondary" onClick={() => setDeletingId(null)}>
                                                    Cancel
                                                </Button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-between gap-3">
                                            <div>
                                                <p className="text-sm font-medium text-slate-200">{group.name}</p>
                                                <p className="text-xs text-slate-400">
                                                    Suppress window: {formatSuppressTime(group.cross_suppress_sec)}
                                                </p>
                                            </div>
                                            <div className="flex gap-1.5">
                                                <Button
                                                    size="icon-sm"
                                                    variant="outline"
                                                    className="border-amber-500/40 bg-amber-500/10 text-amber-200 hover:bg-amber-500/20"
                                                    onClick={() => startEdit(group)}
                                                    title="Edit group"
                                                >
                                                    <PencilLine className="size-3.5" />
                                                </Button>
                                                <Button
                                                    size="icon-sm"
                                                    variant="destructive"
                                                    onClick={() => { setDeletingId(group.id); setEditingId(null) }}
                                                    title="Delete group"
                                                >
                                                    <Trash2 className="size-3.5" />
                                                </Button>
                                            </div>
                                        </div>
                                    )}
                                </li>
                            ))}
                        </ul>
                    )}

                    {/* Create form */}
                    {showCreate && (
                        <div className="mt-3 rounded-lg border border-blue-500/30 bg-blue-500/5 px-4 py-3 space-y-2">
                            <p className="text-xs font-medium uppercase tracking-widest text-slate-400">New group</p>
                            <input
                                autoFocus
                                type="text"
                                value={createName}
                                onChange={(e) => setCreateName(e.target.value)}
                                placeholder="e.g. Main Gate"
                                className="w-full rounded border border-slate-600 bg-slate-700 px-2 py-1.5 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none"
                                onKeyDown={(e) => { if (e.key === "Enter") void handleCreate() }}
                            />
                            <div className="flex items-center gap-2">
                                <label className="text-xs text-slate-400 whitespace-nowrap">Suppress window (sec):</label>
                                <input
                                    type="number"
                                    min="0"
                                    value={createSuppress}
                                    onChange={(e) => setCreateSuppress(e.target.value)}
                                    className="w-24 rounded border border-slate-600 bg-slate-700 px-2 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
                                />
                                <span className="text-xs text-slate-500">= {formatSuppressTime(parseInt(createSuppress) || 0)}</span>
                            </div>
                            <div className="flex gap-2">
                                <Button size="sm" onClick={() => void handleCreate()} disabled={createBusy || !createName.trim()}>
                                    {createBusy ? "Creating..." : "Create"}
                                </Button>
                                <Button size="sm" variant="secondary" onClick={() => { setShowCreate(false); setCreateName(""); setCreateSuppress("120") }}>
                                    Cancel
                                </Button>
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="border-t border-slate-700/80 px-6 py-3">
                    <Button
                        size="sm"
                        variant="secondary"
                        className="gap-1.5"
                        onClick={() => { setShowCreate(true); setEditingId(null); setDeletingId(null) }}
                        disabled={showCreate}
                    >
                        <Plus className="size-4" />
                        New Group
                    </Button>
                </div>
            </div>
        </div>
    )
}
