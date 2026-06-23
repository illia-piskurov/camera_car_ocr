"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Plus, Search, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { addWhitelistPlate, deleteWhitelistPlate, listWhitelist, updateWhitelistPlate } from "@/lib/api"
import type { WhitelistEntry } from "@/lib/types"

const PAGE_SIZE = 100

function formatDate(value: string | null | undefined) {
    if (!value) return "—"
    return new Date(value).toLocaleString("uk-UA", {
        day: "2-digit",
        month: "2-digit",
        year: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    })
}

function SourceBadge({ source }: { source: string }) {
    if (source === "manual") {
        return <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-[10px] font-medium text-blue-300">manual</span>
    }
    if (source === "1c_http") {
        return <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-medium text-emerald-300">1C</span>
    }
    return <span className="rounded-full bg-slate-600/50 px-2 py-0.5 text-[10px] font-medium text-slate-400">{source}</span>
}

function DecisionChip({ decision }: { decision: string | null }) {
    if (!decision) return <span className="text-slate-500">—</span>
    if (decision === "open") return <span className="text-emerald-400">open</span>
    if (decision === "deny") return <span className="text-red-400">deny</span>
    return <span className="text-slate-400">{decision}</span>
}

type WhitelistPanelProps = {
    onClose: () => void
}

export function WhitelistPanel({ onClose }: WhitelistPanelProps) {
    const [entries, setEntries] = useState<WhitelistEntry[]>([])
    const [total, setTotal] = useState(0)
    const [hasMore, setHasMore] = useState(false)
    const [loading, setLoading] = useState(false)
    const [loadingMore, setLoadingMore] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const [searchInput, setSearchInput] = useState("")
    const [debouncedSearch, setDebouncedSearch] = useState("")
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    // Add form
    const [addPlate, setAddPlate] = useState("")
    const [addNote, setAddNote] = useState("")
    const [addBusy, setAddBusy] = useState(false)
    const [addError, setAddError] = useState<string | null>(null)

    // Inline note editing
    const [editingNoteId, setEditingNoteId] = useState<number | null>(null)
    const [editingNoteValue, setEditingNoteValue] = useState("")

    useEffect(() => {
        if (debounceRef.current) clearTimeout(debounceRef.current)
        debounceRef.current = setTimeout(() => setDebouncedSearch(searchInput), 350)
        return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
    }, [searchInput])

    const fetchInitial = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const result = await listWhitelist({ search: debouncedSearch || undefined, offset: 0, limit: PAGE_SIZE })
            setEntries(result.entries)
            setTotal(result.total)
            setHasMore(result.offset + result.entries.length < result.total)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to load whitelist")
        } finally {
            setLoading(false)
        }
    }, [debouncedSearch])

    useEffect(() => { void fetchInitial() }, [fetchInitial])

    async function loadMore() {
        setLoadingMore(true)
        try {
            const result = await listWhitelist({ search: debouncedSearch || undefined, offset: entries.length, limit: PAGE_SIZE })
            setEntries((prev) => {
                const ids = new Set(prev.map((e) => e.id))
                return [...prev, ...result.entries.filter((e) => !ids.has(e.id))]
            })
            setTotal(result.total)
            setHasMore(result.offset + result.entries.length < result.total)
        } catch { /* ignore */ } finally {
            setLoadingMore(false)
        }
    }

    async function handleAdd() {
        const plate = addPlate.trim()
        if (!plate) return
        setAddBusy(true)
        setAddError(null)
        try {
            await addWhitelistPlate(plate, addNote.trim())
            setAddPlate("")
            setAddNote("")
            await fetchInitial()
        } catch (e) {
            setAddError(e instanceof Error ? e.message : "Failed to add plate")
        } finally {
            setAddBusy(false)
        }
    }

    async function handleToggleActive(entry: WhitelistEntry) {
        try {
            const updated = await updateWhitelistPlate(entry.id, { is_active: !entry.is_active })
            setEntries((prev) => prev.map((e) => (e.id === updated.id ? { ...e, ...updated } : e)))
        } catch { /* ignore */ }
    }

    async function handleSaveNote(id: number) {
        try {
            const updated = await updateWhitelistPlate(id, { note: editingNoteValue.trim() || null })
            setEntries((prev) => prev.map((e) => (e.id === updated.id ? { ...e, ...updated } : e)))
        } catch { /* ignore */ } finally {
            setEditingNoteId(null)
        }
    }

    async function handleDelete(entry: WhitelistEntry) {
        try {
            await deleteWhitelistPlate(entry.id)
            setEntries((prev) => prev.filter((e) => e.id !== entry.id))
            setTotal((t) => t - 1)
        } catch { /* ignore */ }
    }

    useEffect(() => {
        const prev = document.body.style.overflow
        document.body.style.overflow = "hidden"
        return () => { document.body.style.overflow = prev }
    }, [])

    useEffect(() => {
        function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose() }
        document.addEventListener("keydown", onKey)
        return () => document.removeEventListener("keydown", onKey)
    }, [onClose])

    return (
        <div className="fixed inset-0 z-40 flex flex-col bg-slate-900">
            {/* Header */}
            <div className="flex shrink-0 items-center justify-between border-b border-slate-700/80 px-6 py-4">
                <div>
                    <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-200">Whitelist</h2>
                    {!loading && (
                        <p className="text-xs text-slate-400">{total} plates total</p>
                    )}
                </div>
                <button type="button" onClick={onClose} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200" aria-label="Close">
                    <X className="size-5" />
                </button>
            </div>

            {/* Search + Add form */}
            <div className="shrink-0 border-b border-slate-700/60 bg-slate-900/80 px-6 py-3 space-y-3">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Search by plate or note…"
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                        className="w-full rounded-lg border border-slate-600/70 bg-slate-800/70 py-2 pl-9 pr-3 text-sm text-slate-100 placeholder-slate-500 focus:border-blue-500/60 focus:outline-none"
                    />
                </div>

                <div className="flex gap-2">
                    <input
                        type="text"
                        placeholder="Plate number (e.g. АА1234ВЕ)"
                        value={addPlate}
                        onChange={(e) => setAddPlate(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") void handleAdd() }}
                        className="w-40 rounded-lg border border-slate-600/70 bg-slate-800/70 px-3 py-1.5 text-sm text-slate-100 placeholder-slate-500 focus:border-blue-500/60 focus:outline-none"
                    />
                    <input
                        type="text"
                        placeholder="Note (optional)"
                        value={addNote}
                        onChange={(e) => setAddNote(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") void handleAdd() }}
                        className="flex-1 rounded-lg border border-slate-600/70 bg-slate-800/70 px-3 py-1.5 text-sm text-slate-100 placeholder-slate-500 focus:border-blue-500/60 focus:outline-none"
                    />
                    <Button
                        size="sm"
                        onClick={() => void handleAdd()}
                        disabled={addBusy || !addPlate.trim()}
                        className="gap-1.5 border border-blue-500/40 bg-blue-500/15 text-blue-200 hover:bg-blue-500/25"
                    >
                        <Plus className="size-4" />
                        Add
                    </Button>
                </div>
                {addError && <p className="text-xs text-red-400">{addError}</p>}
            </div>

            {/* Table */}
            <div className="flex-1 overflow-y-auto">
                {loading ? (
                    <div className="flex h-40 items-center justify-center text-sm text-slate-400">Loading…</div>
                ) : error ? (
                    <div className="flex h-40 items-center justify-center text-sm text-red-400">{error}</div>
                ) : entries.length === 0 ? (
                    <div className="flex h-40 items-center justify-center text-sm text-slate-500">No plates found</div>
                ) : (
                    <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-slate-900/95 text-left text-xs uppercase tracking-wider text-slate-500">
                            <tr>
                                <th className="px-4 py-2 font-medium">Plate</th>
                                <th className="px-4 py-2 font-medium">Source</th>
                                <th className="px-4 py-2 font-medium">Note</th>
                                <th className="px-4 py-2 font-medium">Last seen</th>
                                <th className="px-4 py-2 font-medium">Decision</th>
                                <th className="px-4 py-2 font-medium">Active</th>
                                <th className="px-4 py-2 font-medium"></th>
                            </tr>
                        </thead>
                        <tbody>
                            {entries.map((entry) => (
                                <tr key={entry.id} className={`border-t border-slate-800/70 hover:bg-slate-800/30 ${!entry.is_active ? "opacity-50" : ""}`}>
                                    <td className="px-4 py-2 font-mono font-medium text-slate-100">{entry.plate}</td>
                                    <td className="px-4 py-2"><SourceBadge source={entry.source} /></td>
                                    <td className="px-4 py-2 text-slate-400 max-w-[200px]">
                                        {editingNoteId === entry.id ? (
                                            <div className="flex items-center gap-1">
                                                <input
                                                    autoFocus
                                                    type="text"
                                                    value={editingNoteValue}
                                                    onChange={(e) => setEditingNoteValue(e.target.value)}
                                                    onKeyDown={(e) => {
                                                        if (e.key === "Enter") void handleSaveNote(entry.id)
                                                        if (e.key === "Escape") setEditingNoteId(null)
                                                    }}
                                                    className="w-full rounded border border-slate-600/70 bg-slate-800 px-2 py-0.5 text-xs text-slate-100 focus:outline-none"
                                                />
                                                <button type="button" onClick={() => void handleSaveNote(entry.id)} className="text-xs text-blue-400 hover:text-blue-300">✓</button>
                                                <button type="button" onClick={() => setEditingNoteId(null)} className="text-xs text-slate-500 hover:text-slate-300">✕</button>
                                            </div>
                                        ) : (
                                            <button
                                                type="button"
                                                onClick={() => { setEditingNoteId(entry.id); setEditingNoteValue(entry.note ?? "") }}
                                                className="w-full text-left truncate hover:text-slate-200"
                                                title="Click to edit note"
                                            >
                                                {entry.note || <span className="text-slate-600 italic">add note…</span>}
                                            </button>
                                        )}
                                    </td>
                                    <td className="px-4 py-2 text-xs text-slate-400 whitespace-nowrap">{formatDate(entry.last_event_at)}</td>
                                    <td className="px-4 py-2 text-xs"><DecisionChip decision={entry.last_decision} /></td>
                                    <td className="px-4 py-2">
                                        <button
                                            type="button"
                                            role="switch"
                                            aria-checked={entry.is_active}
                                            onClick={() => void handleToggleActive(entry)}
                                            className={`relative inline-flex h-5 w-9 items-center rounded-full border transition ${entry.is_active ? "border-emerald-500/50 bg-emerald-500/25" : "border-slate-600 bg-slate-700/50"}`}
                                        >
                                            <span className={`inline-block h-3 w-3 rounded-full transition ${entry.is_active ? "translate-x-4 bg-emerald-400" : "translate-x-1 bg-slate-500"}`} />
                                        </button>
                                    </td>
                                    <td className="px-4 py-2">
                                        {entry.source === "manual" && (
                                            <button
                                                type="button"
                                                onClick={() => void handleDelete(entry)}
                                                className="rounded p-1 text-slate-500 hover:bg-red-500/15 hover:text-red-400"
                                                title="Delete manual plate"
                                            >
                                                <X className="size-4" />
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}

                {hasMore && (
                    <div className="flex justify-center p-4">
                        <Button variant="secondary" size="sm" onClick={() => void loadMore()} disabled={loadingMore}>
                            {loadingMore ? "Loading…" : `Load more (${total - entries.length} remaining)`}
                        </Button>
                    </div>
                )}
            </div>
        </div>
    )
}
