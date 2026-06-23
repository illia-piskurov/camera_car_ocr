"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { useState, Suspense } from "react"
import { Camera } from "lucide-react"

function LoginForm() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const [username, setUsername] = useState("")
    const [password, setPassword] = useState("")
    const [error, setError] = useState<string | null>(null)
    const [busy, setBusy] = useState(false)

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        setBusy(true)
        setError(null)
        try {
            const res = await fetch("/api/auth", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            })
            if (!res.ok) {
                setError("Невірний логін або пароль")
                return
            }
            const from = searchParams.get("from") ?? "/"
            router.push(from)
            router.refresh()
        } catch {
            setError("Помилка з'єднання")
        } finally {
            setBusy(false)
        }
    }

    return (
        <div className="flex min-h-svh items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4">
            <div className="w-full max-w-sm">
                <div className="mb-8 flex flex-col items-center gap-3">
                    <div className="flex size-14 items-center justify-center rounded-2xl border border-slate-600/70 bg-slate-800/70 shadow-lg">
                        <Camera className="size-7 text-slate-200" />
                    </div>
                    <div className="text-center">
                        <h1 className="text-lg font-semibold text-slate-100">Camera Car OCR</h1>
                        <p className="text-sm text-slate-400">Введіть дані для входу</p>
                    </div>
                </div>

                <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
                    <div>
                        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-slate-400">
                            Логін
                        </label>
                        <input
                            type="text"
                            autoComplete="username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                            className="w-full rounded-lg border border-slate-600/70 bg-slate-800/70 px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-blue-500/60 focus:outline-none"
                        />
                    </div>

                    <div>
                        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-slate-400">
                            Пароль
                        </label>
                        <input
                            type="password"
                            autoComplete="current-password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            className="w-full rounded-lg border border-slate-600/70 bg-slate-800/70 px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-blue-500/60 focus:outline-none"
                        />
                    </div>

                    {error && (
                        <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
                            {error}
                        </p>
                    )}

                    <button
                        type="submit"
                        disabled={busy}
                        className="w-full rounded-lg border border-blue-500/40 bg-blue-500/20 px-4 py-2.5 text-sm font-medium text-blue-200 transition hover:bg-blue-500/30 disabled:opacity-50"
                    >
                        {busy ? "Вхід…" : "Увійти"}
                    </button>
                </form>
            </div>
        </div>
    )
}

export default function LoginPage() {
    return (
        <Suspense>
            <LoginForm />
        </Suspense>
    )
}
