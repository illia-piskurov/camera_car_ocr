"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { createCamera, validateCamera } from "@/lib/api"
import type { Camera, CameraCreatePayload } from "@/lib/types"

interface OnboardingPanelProps {
    onCameraAdded: (camera: Camera) => void
}

export function OnboardingPanel({ onCameraAdded }: OnboardingPanelProps) {
    const [step, setStep] = useState<"welcome" | "form">("welcome")
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [validating, setValidating] = useState(false)

    const [formData, setFormData] = useState<CameraCreatePayload>({
        name: "",
        snapshot_url: "",
        username: "",
        password: "",
        auth_mode: "http_basic",
    })

    async function handleValidate() {
        setValidating(true)
        setError(null)

        try {
            const result = await validateCamera(formData)
            if (!result.available) {
                setError("Camera is not accessible. Please check the URL, username, and password.")
                return
            }
            // If validation passed, proceed to create
            handleCreate()
        } catch (err) {
            setError(err instanceof Error ? err.message : "Validation failed")
        } finally {
            setValidating(false)
        }
    }

    async function handleCreate() {
        setLoading(true)
        setError(null)

        try {
            const result = await createCamera(formData)
            onCameraAdded(result.camera)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to create camera")
        } finally {
            setLoading(false)
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
                        onClick={() => {
                            setStep("welcome")
                            setError(null)
                            setFormData({
                                name: "",
                                snapshot_url: "",
                                username: "",
                                password: "",
                                auth_mode: "http_basic",
                            })
                        }}
                        className="text-blue-400 hover:text-blue-300 text-sm font-medium"
                    >
                        ← Back
                    </button>
                </div>

                <div className="bg-slate-700 rounded-lg p-8 shadow-xl">
                    <h2 className="text-2xl font-semibold text-white mb-6">Add Camera</h2>

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
                                placeholder="admin"
                                value={formData.username}
                                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                className="w-full px-3 py-2 bg-slate-600 text-white placeholder-slate-400 rounded border border-slate-500 focus:border-blue-500 focus:outline-none"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
                            <input
                                type="password"
                                placeholder="••••••••"
                                value={formData.password}
                                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                className="w-full px-3 py-2 bg-slate-600 text-white placeholder-slate-400 rounded border border-slate-500 focus:border-blue-500 focus:outline-none"
                            />
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
                    </div>

                    <div className="flex gap-3 mt-6">
                        <Button
                            onClick={() => {
                                setStep("welcome")
                                setError(null)
                            }}
                            variant="outline"
                            className="flex-1"
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleValidate}
                            disabled={
                                !formData.name ||
                                !formData.snapshot_url ||
                                !formData.username ||
                                !formData.password ||
                                loading ||
                                validating
                            }
                            className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                        >
                            {validating ? "Validating..." : loading ? "Adding..." : "Add Camera"}
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    )
}
