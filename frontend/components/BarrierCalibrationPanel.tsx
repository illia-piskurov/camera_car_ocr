"use client"

import { useCallback, useEffect, useState } from "react"
import { X, RefreshCw, Check, ChevronDown, ChevronUp, Camera } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
    applyBarrierCalibration,
    captureCalibrationFrames,
    clearBarrierCalibration,
    getBarrierCalibration,
    setCalibrationLabel,
    setCalibrationReference,
} from "@/lib/api"
import type { Barrier, CalibrationData, CalibrationSample } from "@/lib/types"

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_API_BASE ?? "http://192.168.100.112:8000"

interface BarrierCalibrationPanelProps {
    barrier: Barrier
    onClose: () => void
    onBarrierUpdated: (barrier: Barrier) => void
}

function PredictionBadge({
    sample,
    threshold,
    hasModel,
}: {
    sample: CalibrationSample
    threshold: number
    hasModel: boolean
}) {
    if (hasModel && sample.model_prob !== null) {
        const isOpen = sample.model_prob >= 0.5
        return (
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${isOpen ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"}`}>
                {isOpen ? "OPEN" : "CLOSED"} {(sample.model_prob * 100).toFixed(0)}%
            </span>
        )
    }
    if (sample.diff_score === null) return <span className="text-slate-500 text-[10px]">no ref</span>
    const isOpen = sample.diff_score > threshold
    return (
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${isOpen ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"}`}>
            {isOpen ? "OPEN" : "CLOSED"} Δ{(sample.diff_score * 100).toFixed(1)}%
        </span>
    )
}

function SampleCard({
    sample,
    threshold,
    hasModel,
    onLabel,
    onSetReference,
    isSettingRef,
}: {
    sample: CalibrationSample
    threshold: number
    hasModel: boolean
    onLabel: (label: "open" | "closed" | null) => void
    onSetReference: () => void
    isSettingRef: boolean
}) {
    const [showFull, setShowFull] = useState(false)
    const userLabel = sample.user_label

    return (
        <div className={`rounded-lg border p-2 space-y-2 ${userLabel === "closed" ? "border-red-500/40 bg-red-500/5" : userLabel === "open" ? "border-emerald-500/40 bg-emerald-500/5" : "border-slate-700/60 bg-slate-800/50"}`}>
            {/* Crop */}
            {sample.crop_b64 && (
                <div className="overflow-hidden rounded border border-slate-700/50">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                        src={`data:image/jpeg;base64,${sample.crop_b64}`}
                        alt="Barrier zone crop"
                        className="h-16 w-full object-cover"
                    />
                </div>
            )}

            {/* Meta */}
            <div className="flex items-center justify-between gap-1">
                <div className="min-w-0">
                    <p className="truncate text-[10px] text-slate-400">
                        {sample.occurred_at ? new Date(sample.occurred_at).toLocaleString("uk-UA", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—"}
                    </p>
                    <PredictionBadge sample={sample} threshold={threshold} hasModel={hasModel} />
                </div>
                <button
                    type="button"
                    onClick={() => setShowFull(!showFull)}
                    className="shrink-0 rounded p-1 text-slate-500 hover:text-slate-300"
                    title="Show full photo"
                >
                    {showFull ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
            </div>

            {showFull && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                    src={`${API_BASE}${sample.image_url}`}
                    alt="Event snapshot"
                    className="w-full rounded border border-slate-700/50 object-contain"
                />
            )}

            {/* Label buttons */}
            <div className="flex gap-1.5">
                <button
                    type="button"
                    onClick={() => onLabel(userLabel === "closed" ? null : "closed")}
                    className={`flex-1 rounded py-1 text-[11px] font-medium transition ${userLabel === "closed" ? "bg-red-600/80 text-red-50" : "border border-red-500/40 bg-red-500/10 text-red-300 hover:bg-red-500/20"}`}
                >
                    {userLabel === "closed" ? <Check size={11} className="inline mr-1" /> : null}Closed
                </button>
                <button
                    type="button"
                    onClick={() => onLabel(userLabel === "open" ? null : "open")}
                    className={`flex-1 rounded py-1 text-[11px] font-medium transition ${userLabel === "open" ? "bg-emerald-600/80 text-emerald-50" : "border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20"}`}
                >
                    {userLabel === "open" ? <Check size={11} className="inline mr-1" /> : null}Open
                </button>
            </div>

            {/* Set as reference */}
            <button
                type="button"
                onClick={onSetReference}
                disabled={isSettingRef}
                className="w-full rounded border border-amber-500/30 bg-amber-500/5 py-0.5 text-[10px] text-amber-300 hover:bg-amber-500/15 disabled:opacity-40"
            >
                {isSettingRef ? "Setting..." : "Set as closed reference"}
            </button>
        </div>
    )
}

const LIMIT_OPTIONS = [60, 100, 200, 500, 1000, 2000]

export function BarrierCalibrationPanel({ barrier, onClose, onBarrierUpdated }: BarrierCalibrationPanelProps) {
    const [data, setData] = useState<CalibrationData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [limit, setLimit] = useState(100)
    const [applyResult, setApplyResult] = useState<{
        threshold: number
        diff_accuracy: number | null
        model_accuracy: number | null
        n_open: number
        n_closed: number
        n_total_labeled: number
    } | null>(null)
    const [applyBusy, setApplyBusy] = useState(false)
    const [clearBusy, setClearBusy] = useState(false)
    const [captureBusy, setCaptureBusy] = useState(false)
    const [captureCount, setCaptureCount] = useState(3)
    const [captureMsg, setCaptureMsg] = useState<string | null>(null)
    const [settingRefFor, setSettingRefFor] = useState<number | null>(null)
    const [pendingLabels, setPendingLabels] = useState<Record<number, boolean>>({})

    const load = useCallback(async (lim: number) => {
        setLoading(true)
        setError(null)
        try {
            const result = await getBarrierCalibration(barrier.id, lim)
            setData(result)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load calibration data")
        } finally {
            setLoading(false)
        }
    }, [barrier.id])

    useEffect(() => {
        void load(limit)
    }, [load, limit])

    async function handleLabel(eventId: number, label: "open" | "closed" | null) {
        setPendingLabels((prev) => ({ ...prev, [eventId]: true }))
        try {
            await setCalibrationLabel(barrier.id, eventId, label)
            setData((prev) => {
                if (!prev) return prev
                return {
                    ...prev,
                    samples: prev.samples.map((s) =>
                        s.event_id === eventId ? { ...s, user_label: label } : s
                    ),
                }
            })
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save label")
        } finally {
            setPendingLabels((prev) => ({ ...prev, [eventId]: false }))
        }
    }

    async function handleSetReference(eventId: number) {
        setSettingRefFor(eventId)
        setError(null)
        try {
            const updatedBarrier = await setCalibrationReference(barrier.id, eventId)
            onBarrierUpdated(updatedBarrier)
            await load(limit)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to set reference")
        } finally {
            setSettingRefFor(null)
        }
    }

    async function handleCapture() {
        setCaptureBusy(true)
        setCaptureMsg(null)
        setError(null)
        try {
            const result = await captureCalibrationFrames(barrier.id, captureCount)
            setCaptureMsg(`Captured ${result.captured.length} frame${result.captured.length !== 1 ? "s" : ""}`)
            await load(limit)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Capture failed")
        } finally {
            setCaptureBusy(false)
        }
    }

    async function handleApply() {
        setApplyBusy(true)
        setError(null)
        setApplyResult(null)
        try {
            const result = await applyBarrierCalibration(barrier.id)
            setApplyResult(result)
            await load(limit)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to apply calibration")
        } finally {
            setApplyBusy(false)
        }
    }

    async function handleClear() {
        setClearBusy(true)
        setError(null)
        try {
            await clearBarrierCalibration(barrier.id)
            await load(limit)
            setApplyResult(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to clear labels")
        } finally {
            setClearBusy(false)
        }
    }

    const threshold = data?.threshold ?? barrier.state_threshold
    const hasModel = data?.has_model ?? barrier.has_model
    const samples = data?.samples ?? []
    const nLabeled = samples.filter((s) => s.user_label).length
    const nClosed = samples.filter((s) => s.user_label === "closed").length
    const nOpen = samples.filter((s) => s.user_label === "open").length
    const canApply = data?.has_reference && nClosed >= 1 && nOpen >= 1

    return (
        <div className="fixed inset-0 z-50 flex items-start justify-end bg-black/50 p-4">
            <div className="flex h-full w-full max-w-2xl flex-col rounded-xl border border-slate-700/90 bg-slate-900 shadow-2xl">
                {/* Header */}
                <div className="flex shrink-0 items-center justify-between border-b border-slate-700/70 px-4 py-3">
                    <div>
                        <h2 className="text-sm font-semibold text-slate-200">
                            Calibrate: {barrier.name || `Barrier ${barrier.id}`}
                        </h2>
                        <p className="text-[11px] text-slate-500">Label event photos to train the open/closed detector</p>
                    </div>
                    <div className="flex items-center gap-2">
                        {/* Limit selector */}
                        <select
                            value={limit}
                            onChange={(e) => setLimit(Number(e.target.value))}
                            className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-[11px] text-slate-300 outline-none focus:border-amber-400"
                            title="Number of photos to load"
                        >
                            {LIMIT_OPTIONS.map((n) => (
                                <option key={n} value={n}>{n} photos</option>
                            ))}
                        </select>
                        <button
                            type="button"
                            onClick={() => void load(limit)}
                            disabled={loading}
                            className="rounded p-1.5 text-slate-400 hover:bg-slate-700/60 hover:text-slate-100"
                            title="Reload"
                        >
                            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
                        </button>
                        <button
                            type="button"
                            onClick={onClose}
                            className="rounded p-1 text-slate-400 hover:bg-slate-700/60 hover:text-slate-100"
                        >
                            <X size={18} />
                        </button>
                    </div>
                </div>

                {/* Status bar */}
                <div className="shrink-0 border-b border-slate-700/60 px-4 py-2 flex flex-wrap items-center gap-3 text-[11px]">
                    <span className={`rounded px-2 py-0.5 ${data?.has_reference ? "bg-amber-500/20 text-amber-300" : "bg-slate-700/60 text-slate-400"}`}>
                        {data?.has_reference ? `Reference set (event #${data.reference_event_id})` : "No reference — pick one below"}
                    </span>
                    {hasModel ? (
                        <span className="rounded px-2 py-0.5 bg-violet-500/20 text-violet-300">
                            Model active
                        </span>
                    ) : (
                        <span className="text-slate-400">
                            Threshold: <span className="text-slate-200">{(threshold * 100).toFixed(1)}%</span>
                        </span>
                    )}
                    <span className="text-slate-400">
                        Labeled: <span className="text-red-300">{nClosed} closed</span> / <span className="text-emerald-300">{nOpen} open</span>
                    </span>
                    {applyResult && (
                        <span className="text-violet-300">
                            Trained on {applyResult.n_total_labeled} samples
                            {applyResult.model_accuracy !== null && ` · model ${(applyResult.model_accuracy * 100).toFixed(0)}%`}
                            {applyResult.diff_accuracy !== null && ` · diff ${(applyResult.diff_accuracy * 100).toFixed(0)}%`}
                        </span>
                    )}
                </div>

                {error && (
                    <div className="shrink-0 px-4 py-2 text-xs text-red-300 bg-red-500/10 border-b border-red-500/20">
                        {error}
                    </div>
                )}

                {/* Instructions */}
                {!data?.has_reference && !loading && (
                    <div className="shrink-0 px-4 py-2 text-[11px] text-amber-300/80 bg-amber-500/5 border-b border-amber-500/20">
                        Step 1: Find a photo where the barrier is clearly <strong>CLOSED</strong> and click &quot;Set as closed reference&quot;.
                        Step 2: Label other photos as Open or Closed.
                        Step 3: Click &quot;Apply&quot; to train the model.
                    </div>
                )}

                {/* Photos grid */}
                <div className="flex-1 overflow-y-auto px-4 py-3">
                    {loading && <p className="text-sm text-slate-400">Loading event photos…</p>}
                    {data?.error && <p className="text-sm text-amber-300">{data.error}</p>}
                    {!loading && samples.length === 0 && !data?.error && (
                        <p className="text-sm text-slate-500">No event snapshots found for this barrier&apos;s camera.</p>
                    )}
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                        {samples.map((sample) => (
                            <SampleCard
                                key={sample.event_id}
                                sample={sample}
                                threshold={threshold}
                                hasModel={hasModel}
                                onLabel={(label) => void handleLabel(sample.event_id, label)}
                                onSetReference={() => void handleSetReference(sample.event_id)}
                                isSettingRef={settingRefFor === sample.event_id}
                            />
                        ))}
                    </div>
                </div>

                {/* Footer */}
                <div className="shrink-0 border-t border-slate-700/70 px-4 py-3 space-y-2">
                    {/* Capture row */}
                    <div className="flex items-center gap-2">
                        <Camera size={14} className="shrink-0 text-slate-400" />
                        <span className="text-[11px] text-slate-400">Capture live frame:</span>
                        <select
                            value={captureCount}
                            onChange={(e) => setCaptureCount(Number(e.target.value))}
                            disabled={captureBusy}
                            className="rounded border border-slate-600 bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300 outline-none focus:border-sky-400 disabled:opacity-40"
                        >
                            {[1, 2, 3, 5, 10].map((n) => (
                                <option key={n} value={n}>{n}</option>
                            ))}
                        </select>
                        <Button
                            size="sm"
                            onClick={() => void handleCapture()}
                            disabled={captureBusy}
                            className="border border-sky-500/40 bg-sky-600/70 text-sky-50 hover:bg-sky-500/80 disabled:opacity-40 px-3 py-1 text-[11px]"
                        >
                            {captureBusy ? "Capturing…" : "Capture"}
                        </Button>
                        {captureMsg && <span className="text-[11px] text-emerald-400">{captureMsg}</span>}
                    </div>
                    {/* Train / clear row */}
                    <div className="flex items-center gap-2">
                        <Button
                            size="sm"
                            onClick={() => void handleApply()}
                            disabled={!canApply || applyBusy}
                            className="flex-1 border border-violet-500/30 bg-violet-600/80 text-violet-50 hover:bg-violet-500 disabled:opacity-40"
                            title={!data?.has_reference ? "Set a reference first" : nLabeled < 2 ? "Label at least 1 open and 1 closed photo" : ""}
                        >
                            {applyBusy ? "Training…" : hasModel ? "Retrain Model" : "Train Model"}
                        </Button>
                        <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => void handleClear()}
                            disabled={clearBusy || nLabeled === 0}
                            className="border border-slate-600/70 bg-slate-700/80 text-slate-300 hover:bg-slate-600/90 disabled:opacity-40"
                        >
                            {clearBusy ? "Clearing…" : "Clear Labels"}
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    )
}
