"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { fetchDashboard, fetchPreview, forceSync, toPreviewImageSrc } from "@/lib/api"
import type { DashboardData, PreviewData } from "@/lib/types"

type UseDashboardState = {
    data: DashboardData | null
    preview: PreviewData | null
    loading: boolean
    error: string | null
    refreshing: boolean
    lastUpdatedAt: Date | null
    isStale: boolean
}

const POLL_MS = 2500
const STALE_MS = 12000

export function useDashboard() {
    const [state, setState] = useState<UseDashboardState>({
        data: null,
        preview: null,
        loading: true,
        error: null,
        refreshing: false,
        lastUpdatedAt: null,
        isStale: false,
    })

    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

    const refresh = useCallback(async () => {
        setState((prev) => ({ ...prev, refreshing: true, error: null }))

        const controller = new AbortController()
        try {
            const [data, preview] = await Promise.all([
                fetchDashboard(controller.signal),
                fetchPreview(controller.signal).catch(() => null),
            ])

            setState((prev) => ({
                ...prev,
                data,
                preview,
                loading: false,
                refreshing: false,
                error: null,
                lastUpdatedAt: new Date(),
                isStale: false,
            }))
        } catch (error) {
            setState((prev) => ({
                ...prev,
                loading: false,
                refreshing: false,
                error: error instanceof Error ? error.message : "Не удалось загрузить данные",
            }))
        }
    }, [])

    const runForceSync = useCallback(async () => {
        await forceSync()
        await refresh()
    }, [refresh])

    useEffect(() => {
        void refresh()

        timerRef.current = setInterval(() => {
            void refresh()
        }, POLL_MS)

        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current)
            }
        }
    }, [refresh])

    useEffect(() => {
        const staleTimer = setInterval(() => {
            setState((prev) => {
                if (!prev.lastUpdatedAt) {
                    return prev
                }

                const age = Date.now() - prev.lastUpdatedAt.getTime()
                return { ...prev, isStale: age > STALE_MS }
            })
        }, 1000)

        return () => clearInterval(staleTimer)
    }, [])

    const derived = useMemo(() => {
        const syncAgeSec = state.data?.sync.sync_age_seconds ?? null
        const previewImageSrc = toPreviewImageSrc(state.preview)
        return {
            syncAgeSec,
            previewImageSrc,
            hasData: Boolean(state.data),
        }
    }, [state.data, state.preview])

    return {
        ...state,
        ...derived,
        refresh,
        runForceSync,
    }
}
