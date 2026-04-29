"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { createCamera, updateCamera, validateCamera } from "@/lib/api"
import type { Camera, CameraCreatePayload, CameraUpdatePayload } from "@/lib/types"

interface OnboardingPanelProps {
    mode: "create" | "edit"
    camera?: Camera | null
    onCameraSaved: (camera: Camera) => void
    onCancel?: () => void
    isFirstCameraFlow?: boolean
}

type CameraFormValues = {
    name: string
    snapshot_url: string
    username: string
    password: string
    auth_mode: string
    sort_order: string
}

function buildInitialFormValues(mode: "create" | "edit", camera?: Camera | null): CameraFormValues {
    if (mode === "edit" && camera) {
        return {
            name: camera.name,
            snapshot_url: camera.snapshot_url,
            username: "",
            password: "",
            auth_mode: camera.auth_mode,
            sort_order: String(camera.sort_order),
        }
    }

    return {
        name: "",
        snapshot_url: "",
        username: "",
        password: "",
        auth_mode: "http_basic",
        sort_order: "",
    }
}

function buildSortOrder(value: string): number | undefined {
    const trimmed = value.trim()
    if (!trimmed) {
        return undefined
    }

    const parsed = Number(trimmed)
    return Number.isFinite(parsed) ? parsed : undefined
}

export function OnboardingPanel({ mode, camera, onCameraSaved, onCancel, isFirstCameraFlow = true }: OnboardingPanelProps) {
    const isCreateMode = mode === "create"
    const [step, setStep] = useState<"welcome" | "form">(isFirstCameraFlow && isCreateMode ? "welcome" : "form")
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [validating, setValidating] = useState(false)

    const [formData, setFormData] = useState<CameraFormValues>(() => buildInitialFormValues(mode, camera))

    useEffect(() => {
        setStep(isFirstCameraFlow && isCreateMode ? "welcome" : "form")
        setError(null)
        setFormData(buildInitialFormValues(mode, camera))
    }, [camera?.id, isCreateMode, isFirstCameraFlow, mode])

    async function handleValidate() {
        setValidating(true)
        setError(null)

        try {
            const payload: CameraCreatePayload = {
                name: formData.name.trim(),
                snapshot_url: formData.snapshot_url.trim(),
                username: formData.username.trim(),
                password: formData.password,
                auth_mode: formData.auth_mode,
                sort_order: buildSortOrder(formData.sort_order),
            }
            const result = await validateCamera(payload)
            if (!result.available) {
                setError("Camera is not accessible. Please check the URL, username, and password.")
                return
            }
            await handleCreate(payload)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Validation failed")
        } finally {
            setValidating(false)
        }
    }

    async function handleCreate(payload?: CameraCreatePayload) {
        setLoading(true)
        setError(null)

        try {
            const nextPayload = payload ?? {
                name: formData.name.trim(),
                snapshot_url: formData.snapshot_url.trim(),
                username: formData.username.trim(),
                password: formData.password,
                auth_mode: formData.auth_mode,
                sort_order: buildSortOrder(formData.sort_order),
            }
            const result = await createCamera(nextPayload)
            onCameraSaved(result.camera)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to create camera")
        } finally {
            setLoading(false)
        }
    }

    async function handleSave() {
        if (!camera) {
            return
        }

        const name = formData.name.trim()
        const snapshotUrl = formData.snapshot_url.trim()
        if (!name || !snapshotUrl) {
            setError("Camera name and snapshot URL are required")
            return
        }

        setLoading(true)
        setError(null)

        try {
            const payload: CameraUpdatePayload = {
                name,
                snapshot_url: snapshotUrl,
                auth_mode: formData.auth_mode,
                sort_order: buildSortOrder(formData.sort_order),
            }

            if (formData.username.trim()) {
                payload.username = formData.username.trim()
            }
            if (formData.password.trim()) {
                payload.password = formData.password
            }

            const result = await updateCamera(camera.id, payload)
            onCameraSaved(result.camera)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to update camera")
        } finally {
            setLoading(false)
        }
    }

    const submitLabel = isCreateMode ? (validating ? "Validating..." : loading ? "Adding..." : "Add Camera") : loading ? "Saving..." : "Save Camera"
    const title = isCreateMode ? "Add Camera" : "Edit Camera"
    function handleBack() {
        if (onCancel && (!isCreateMode || !isFirstCameraFlow)) {
            onCancel()
            return
        }

        if (isCreateMode && isFirstCameraFlow) {
            setStep("welcome")
            setError(null)
        }
    }

    if (step === "welcome") {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4">
                <div className="max-w-md w-full">
                    <div className="mb-8 text-center">
                        <h1 className="text-4xl font-bold text-white mb-2">Camera Car OCR</h1>
                        <p className="text-slate-300">Intelligent license plate recognition system</p>
                    </div>

                    <div className="bg-slate-700 rounded-lg p-8 shadow-xl">
                        <h2 className="text-2xl font-semibold text-white mb-4">Welcome!</h2>
                        <p className="text-slate-300 mb-6 leading-relaxed">
                            This system monitors vehicle license plates in configured zones. Let's get started by adding your
                            first camera.
                        </p>

                        <Button
                            onClick={() => setStep("form")}
                            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded"
                        >
                            Add First Camera
                        </Button>
                        {onCancel && (
                            <Button
                                onClick={onCancel}
                                variant="outline"
                                className="mt-3 w-full"
                            >
                                Back to Dashboard
                            </Button>
                        )}
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4">
            <div className="max-w-md w-full">
                <div className="mb-8">
                    <button
                        onClick={handleBack}
                        className="text-blue-400 hover:text-blue-300 text-sm font-medium"
                    >
                        {isCreateMode && isFirstCameraFlow ? "← Back" : "← Back to Dashboard"}
                    </button>
                </div>

                <div className="bg-slate-700 rounded-lg p-8 shadow-xl">
                    <h2 className="text-2xl font-semibold text-white mb-2">{title}</h2>
                    <p className="mb-6 text-sm text-slate-300">
                        {isCreateMode ? "Add a new camera to the control room." : "Update camera details without re-entering preserved credentials."}
                    </p>

                    {error && (
                        <div className="mb-4 p-3 bg-red-900/50 border border-red-500 rounded text-red-200 text-sm">
                            {error}
                        </div>
                    )}

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1">Camera Name</label>
                            <input
                                type="text"
                                placeholder="e.g., Entrance"
                                value={formData.name}
                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                className="w-full px-3 py-2 bg-slate-600 text-white placeholder-slate-400 rounded border border-slate-500 focus:border-blue-500 focus:outline-none"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1">Snapshot URL</label>
                            <input
                                type="text"
                                placeholder="http://camera.local/snapshot"
                                value={formData.snapshot_url}
                                onChange={(e) => setFormData({ ...formData, snapshot_url: e.target.value })}
                                className="w-full px-3 py-2 bg-slate-600 text-white placeholder-slate-400 rounded border border-slate-500 focus:border-blue-500 focus:outline-none"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1">Username</label>
                            <input
                                type="text"
                                placeholder={isCreateMode ? "admin" : "Leave blank to keep current username"}
                                value={formData.username}
                                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                className="w-full px-3 py-2 bg-slate-600 text-white placeholder-slate-400 rounded border border-slate-500 focus:border-blue-500 focus:outline-none"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
                            <input
                                type="password"
                                placeholder={isCreateMode ? "••••••••" : "Leave blank to keep current password"}
                                value={formData.password}
                                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                className="w-full px-3 py-2 bg-slate-600 text-white placeholder-slate-400 rounded border border-slate-500 focus:border-blue-500 focus:outline-none"
                            />
                            {!isCreateMode && <p className="mt-1 text-xs text-slate-400">Leave blank to keep the current password.</p>}
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1">Auth Mode</label>
                            <select
                                value={formData.auth_mode}
                                onChange={(e) => setFormData({ ...formData, auth_mode: e.target.value })}
                                className="w-full px-3 py-2 bg-slate-600 text-white rounded border border-slate-500 focus:border-blue-500 focus:outline-none"
                            >
                                <option value="http_basic">HTTP Basic</option>
                                <option value="http_digest">HTTP Digest</option>
                                <option value="none">None</option>
                            </select>
                        </div>

                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-1">Sort Order</label>
                                <input
                                    type="number"
                                    min="0"
                                    step="1"
                                    placeholder="Auto"
                                    value={formData.sort_order}
                                    onChange={(e) => setFormData({ ...formData, sort_order: e.target.value })}
                                    className="w-full px-3 py-2 bg-slate-600 text-white placeholder-slate-400 rounded border border-slate-500 focus:border-blue-500 focus:outline-none"
                                />
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-3 mt-6">
                        <Button
                            onClick={() => {
                                if (onCancel && (!isCreateMode || !isFirstCameraFlow)) {
                                    onCancel()
                                } else {
                                    setStep("welcome")
                                    setError(null)
                                }
                            }}
                            variant="outline"
                            className="flex-1"
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={isCreateMode ? handleValidate : handleSave}
                            disabled={
                                !formData.name.trim() ||
                                !formData.snapshot_url.trim() ||
                                (isCreateMode && (!formData.username.trim() || !formData.password.trim())) ||
                                loading ||
                                validating
                            }
                            className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                        >
                            {submitLabel}
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    )
}
