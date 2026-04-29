"use client"

import { useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"

type ConfirmationDialogProps = {
    open: boolean
    title: string
    description: string
    confirmLabel: string
    cancelLabel?: string
    confirmTone?: "default" | "destructive"
    busy?: boolean
    error?: string | null
    onConfirm: () => void
    onCancel: () => void
}

export function ConfirmationDialog({
    open,
    title,
    description,
    confirmLabel,
    cancelLabel = "Cancel",
    confirmTone = "destructive",
    busy = false,
    error = null,
    onConfirm,
    onCancel,
}: ConfirmationDialogProps) {
    const dialogRef = useRef<HTMLDivElement | null>(null)

    useEffect(() => {
        if (!open) {
            return
        }

        function handleKeyDown(event: KeyboardEvent) {
            if (event.key === "Escape") {
                onCancel()
            }
        }

        function handleOutsideClick(event: MouseEvent) {
            if (dialogRef.current && !dialogRef.current.contains(event.target as Node)) {
                onCancel()
            }
        }

        document.addEventListener("keydown", handleKeyDown)
        document.addEventListener("mousedown", handleOutsideClick)

        return () => {
            document.removeEventListener("keydown", handleKeyDown)
            document.removeEventListener("mousedown", handleOutsideClick)
        }
    }, [onCancel, open])

    if (!open) {
        return null
    }

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4">
            <div ref={dialogRef} className="w-full max-w-lg rounded-xl border border-slate-700/90 bg-slate-900 p-5 shadow-2xl">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Confirm action</p>
                <h3 className="mt-2 text-xl font-semibold text-white">{title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-300">{description}</p>

                {error && <div className="mt-4 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</div>}

                <div className="mt-6 flex items-center justify-end gap-3">
                    <Button variant="secondary" onClick={onCancel} disabled={busy}>
                        {cancelLabel}
                    </Button>
                    <Button variant={confirmTone === "destructive" ? "destructive" : "default"} onClick={onConfirm} disabled={busy}>
                        {busy ? "Working..." : confirmLabel}
                    </Button>
                </div>
            </div>
        </div>
    )
}