"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { Camera, ChevronDown, PencilLine, Plus, RefreshCw, Trash2, Zap } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { Camera as CameraModel } from "@/lib/types"

type ControlRoomHeaderProps = {
    cameras: CameraModel[]
    selectedCameraId: number | null
    onSelectCamera: (cameraId: number) => void
    onAddCamera: () => void
    onEditCamera: (camera: CameraModel) => void
    onDeleteCamera: (camera: CameraModel) => void
    syncAgeSec: number | null
    onRefresh: () => void
    onForceSync: () => void
    refreshing?: boolean
}

function formatSyncAge(seconds: number | null) {
    if (seconds === null) {
        return "no sync yet"
    }

    if (seconds < 60) {
        return `${seconds}s ago`
    }

    const min = Math.floor(seconds / 60)
    if (min < 60) {
        return `${min}m ago`
    }

    const hours = Math.floor(min / 60)
    return `${hours}h ago`
}

export function ControlRoomHeader({
    cameras,
    selectedCameraId,
    onSelectCamera,
    onAddCamera,
    onEditCamera,
    onDeleteCamera,
    syncAgeSec,
    onRefresh,
    onForceSync,
    refreshing = false,
}: ControlRoomHeaderProps) {
    const [isCameraMenuOpen, setIsCameraMenuOpen] = useState(false)
    const [highlightedIndex, setHighlightedIndex] = useState(-1)
    const cameraMenuRef = useRef<HTMLDivElement | null>(null)

    const selectedCamera = useMemo(
        () => cameras.find((camera) => camera.id === selectedCameraId) ?? cameras[0] ?? null,
        [cameras, selectedCameraId],
    )

    useEffect(() => {
        function handleOutsideClick(event: MouseEvent) {
            if (!cameraMenuRef.current) {
                return
            }
            if (!cameraMenuRef.current.contains(event.target as Node)) {
                setIsCameraMenuOpen(false)
            }
        }

        function handleEscape(event: KeyboardEvent) {
            if (event.key === "Escape") {
                setIsCameraMenuOpen(false)
                setHighlightedIndex(-1)
            }
        }

        document.addEventListener("mousedown", handleOutsideClick)
        document.addEventListener("keydown", handleEscape)
        return () => {
            document.removeEventListener("mousedown", handleOutsideClick)
            document.removeEventListener("keydown", handleEscape)
        }
    }, [])

    useEffect(() => {
        if (!isCameraMenuOpen) {
            setHighlightedIndex(-1)
            return
        }

        const selectedIndex = selectedCamera
            ? cameras.findIndex((camera) => camera.id === selectedCamera.id)
            : 0
        setHighlightedIndex(selectedIndex >= 0 ? selectedIndex : 0)
    }, [isCameraMenuOpen, cameras, selectedCamera])

    function activateMenuItem(index: number) {
        if (index === cameras.length) {
            setIsCameraMenuOpen(false)
            onAddCamera()
            return
        }

        const camera = cameras[index]
        if (!camera) {
            return
        }
        onSelectCamera(camera.id)
        setIsCameraMenuOpen(false)
    }

    function handleMenuKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
        const itemCount = cameras.length + 1

        if (!isCameraMenuOpen && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
            event.preventDefault()
            setIsCameraMenuOpen(true)
            return
        }

        if (!isCameraMenuOpen) {
            return
        }

        if (event.key === "ArrowDown") {
            event.preventDefault()
            setHighlightedIndex((prev) => (prev + 1 + itemCount) % itemCount)
            return
        }

        if (event.key === "ArrowUp") {
            event.preventDefault()
            setHighlightedIndex((prev) => (prev - 1 + itemCount) % itemCount)
            return
        }

        if (event.key === "Home") {
            event.preventDefault()
            setHighlightedIndex(0)
            return
        }

        if (event.key === "End") {
            event.preventDefault()
            setHighlightedIndex(itemCount - 1)
            return
        }

        if (event.key === "Enter") {
            event.preventDefault()
            const index = highlightedIndex >= 0 ? highlightedIndex : 0
            activateMenuItem(index)
        }
    }

    const syncStatus = syncAgeSec === null ? "⚠ Pending" : "✓ Connected"

    return (
        <header className="sticky top-0 z-40 w-full border-b border-slate-700/80 bg-slate-900/70 backdrop-blur-md">
            <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
                <div className="flex size-10 items-center justify-center rounded-xl border border-slate-600/70 bg-slate-800/70 text-slate-200 shadow-sm shadow-black/20">
                    <Camera className="size-5" />
                </div>

                <div className="relative min-w-[220px] flex-1 sm:max-w-sm" ref={cameraMenuRef}>
                    <button
                        type="button"
                        onClick={() => setIsCameraMenuOpen((open) => !open)}
                        onKeyDown={handleMenuKeyDown}
                        className="flex w-full items-center justify-between gap-2 rounded-xl border border-slate-600/70 bg-slate-800/70 px-3 py-2 text-left text-sm font-medium text-slate-100 transition hover:border-slate-500 hover:bg-slate-700/80"
                        aria-haspopup="menu"
                        aria-expanded={isCameraMenuOpen}
                    >
                        <span className="truncate">{selectedCamera?.name ?? "Select camera"}</span>
                        <ChevronDown className={`size-4 shrink-0 text-slate-300 transition ${isCameraMenuOpen ? "rotate-180" : ""}`} />
                    </button>

                    {isCameraMenuOpen && (
                        <>
                            <div
                                className="fixed inset-0 z-40 bg-black/35 sm:hidden"
                                onClick={() => setIsCameraMenuOpen(false)}
                                aria-hidden="true"
                            />

                            <div className="fixed inset-x-0 top-16 z-50 border-y border-slate-600/80 bg-slate-900/95 px-3 py-3 shadow-xl shadow-black/40 sm:absolute sm:left-0 sm:right-0 sm:top-[calc(100%+8px)] sm:rounded-xl sm:border sm:bg-slate-800/95 sm:p-0">
                                <ul className="max-h-[45vh] overflow-y-auto p-1 sm:max-h-64">
                                    {cameras.map((camera, index) => (
                                        <li key={camera.id}>
                                            <div
                                                className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition ${selectedCamera?.id === camera.id
                                                    ? "bg-blue-500/20 text-blue-200"
                                                    : highlightedIndex === index
                                                        ? "bg-slate-700/80 text-slate-100"
                                                        : "text-slate-200 hover:bg-slate-700/70"
                                                    }`}
                                                onMouseEnter={() => setHighlightedIndex(index)}
                                            >
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        onSelectCamera(camera.id)
                                                        setIsCameraMenuOpen(false)
                                                    }}
                                                    onFocus={() => setHighlightedIndex(index)}
                                                    className="min-w-0 flex-1 rounded-md px-1 py-1 text-left"
                                                >
                                                    <div className="flex items-center justify-between gap-2">
                                                        <span className="truncate">{camera.name}</span>
                                                        {camera.is_active && <span className="text-[11px] uppercase tracking-wide text-slate-400">active</span>}
                                                    </div>
                                                </button>

                                                <div className="flex items-center gap-1">
                                                    <Button
                                                        type="button"
                                                        size="icon-sm"
                                                        variant="outline"
                                                        className="border-amber-500/40 bg-amber-500/10 text-amber-200 hover:bg-amber-500/20 hover:text-amber-100"
                                                        aria-label={`Edit ${camera.name}`}
                                                        title="Edit camera"
                                                        onClick={() => {
                                                            setIsCameraMenuOpen(false)
                                                            onEditCamera(camera)
                                                        }}
                                                    >
                                                        <PencilLine className="size-4" />
                                                    </Button>
                                                    <Button
                                                        type="button"
                                                        size="icon-sm"
                                                        variant="destructive"
                                                        aria-label={`Delete ${camera.name}`}
                                                        title="Delete camera"
                                                        onClick={() => {
                                                            setIsCameraMenuOpen(false)
                                                            onDeleteCamera(camera)
                                                        }}
                                                    >
                                                        <Trash2 className="size-4" />
                                                    </Button>
                                                </div>
                                            </div>
                                        </li>
                                    ))}
                                </ul>

                                <div className="border-t border-slate-600/70 p-1">
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setIsCameraMenuOpen(false)
                                            onAddCamera()
                                        }}
                                        onMouseEnter={() => setHighlightedIndex(cameras.length)}
                                        onFocus={() => setHighlightedIndex(cameras.length)}
                                        className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${highlightedIndex === cameras.length
                                            ? "bg-blue-500/25 text-blue-100"
                                            : "text-blue-200 hover:bg-blue-500/15"
                                            }`}
                                    >
                                        <Plus className="size-4" />
                                        Add camera
                                    </button>
                                </div>
                            </div>
                        </>
                    )}
                </div>

                <Button
                    variant="secondary"
                    size="sm"
                    onClick={onAddCamera}
                    className="gap-2 border border-slate-500/70 bg-slate-700/80 text-slate-100 hover:bg-slate-600/90"
                >
                    <Plus className="size-4" />
                    Add
                </Button>

                <div className="ml-auto flex items-center gap-2">
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={onRefresh}
                        disabled={refreshing}
                        className="gap-2 border border-slate-500/70 bg-slate-700/80 text-slate-100 hover:bg-slate-600/90"
                    >
                        <RefreshCw className={`size-4 ${refreshing ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={onForceSync}
                        className="gap-2 border border-slate-500/70 bg-slate-700/80 text-slate-100 hover:bg-slate-600/90"
                    >
                        <Zap className="size-4" />
                        Force Sync
                    </Button>
                </div>

                <div className="w-full text-xs text-slate-300 sm:w-auto sm:text-right">
                    Last sync: {formatSyncAge(syncAgeSec)} | 1C: {syncStatus}
                </div>
            </div>
        </header>
    )
}
