"use client"

import { AlertCircle, CheckCircle2, RefreshCw, Siren } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { DashboardData, PreviewData, DetectionZone } from "@/lib/types"

type DashboardSidebarProps = {
    data: DashboardData | null
    preview: PreviewData | null
    zones: DetectionZone[]
    maxZones: number
    zonesDirty: boolean
    zonesSaving: boolean
    zonesMessage: string | null
    onSaveZones: () => void
    onResetZones: () => void
    onUpdateZone: (index: number, updater: (zone: DetectionZone) => DetectionZone) => void
    onRemoveZone: (index: number) => void
    syncAgeSec: number | null
}

function formatTime(value: string | null | undefined) {
    if (!value) {
        return "-"
    }
    return new Date(value).toLocaleString("ru-RU")
}

function formatPercent(value: number | null | undefined) {
    const v = value ?? 0
    return `${(v * 100).toFixed(1)}%`
}

function formatSyncAge(seconds: number | null) {
    if (seconds === null) {
        return "нет данных"
    }

    if (seconds < 60) {
        return `${seconds} сек назад`
    }

    const min = Math.floor(seconds / 60)
    if (min < 60) {
        return `${min} мин назад`
    }

    const hours = Math.floor(min / 60)
    return `${hours} ч назад`
}

export function DashboardSidebar({
    data,
    preview,
    zones,
    maxZones,
    zonesDirty,
    zonesSaving,
    zonesMessage,
    onSaveZones,
    onResetZones,
    onUpdateZone,
    onRemoveZone,
    syncAgeSec,
}: DashboardSidebarProps) {
    const visibleZones = [...zones].sort((a, b) => a.sort_order - b.sort_order)

    return (
        <aside className="space-y-4">
            {/* Operational Metrics Section */}
            <section className="space-y-3">
                <h3 className="text-xs uppercase tracking-widest text-zinc-500">Операции</h3>

                {/* Режим открытия */}
                <article className="ops-card">
                    <p className="ops-label">Режим открытия</p>
                    <div className="mt-2 flex items-center gap-2">
                        {data?.mode.dry_run_open ? (
                            <>
                                <AlertCircle className="size-5 text-amber-400" />
                                <span className="text-lg font-semibold text-amber-300">DRY-RUN</span>
                            </>
                        ) : (
                            <>
                                <CheckCircle2 className="size-5 text-emerald-400" />
                                <span className="text-lg font-semibold text-emerald-300">ACTIVE</span>
                            </>
                        )}
                    </div>
                    <p className="mt-2 text-xs text-zinc-400">
                        Подтверждений: {data?.mode.min_confirmations ?? "-"}
                    </p>
                </article>

                {/* Решения за 24ч */}
                <article className="ops-card">
                    <p className="ops-label">Решения за 24ч</p>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-semibold text-emerald-300">{data?.kpi_24h.open ?? 0}</span>
                        <span className="text-sm text-zinc-400">open</span>
                    </div>
                    <p className="mt-1 text-xs text-zinc-400">deny: {data?.kpi_24h.deny ?? 0}</p>
                </article>

                {/* Средняя уверенность */}
                <article className="ops-card">
                    <p className="ops-label">Средняя уверенность</p>
                    <p className="mt-2 text-2xl font-semibold">{formatPercent(data?.kpi_24h.avg_confidence)}</p>
                    <p className="mt-1 text-xs text-zinc-400">последние подтвержденные решения</p>
                </article>
            </section>

            {/* Integration Status Section */}
            <section className="space-y-3 border-t border-zinc-800 pt-4">
                <h3 className="text-xs uppercase tracking-widest text-zinc-500">Интеграции</h3>

                <div className="space-y-2 text-sm">
                    <div className="ops-kv">
                        <span>1С sync</span>
                        <span className={data?.sync.is_due ? "text-amber-300" : "text-emerald-300"}>
                            {data?.sync.is_due ? "требуется" : "актуально"}
                        </span>
                    </div>
                    <div className="ops-kv">
                        <span>Последний sync</span>
                        <span>{formatTime(data?.sync.last_sync_at)}</span>
                    </div>
                    <div className="ops-kv">
                        <span>Возраст sync</span>
                        <span>{formatSyncAge(syncAgeSec)}</span>
                    </div>
                </div>

                <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
                    <p className="text-xs uppercase tracking-widest text-zinc-500">Новый кадр</p>
                    <div className="mt-2 space-y-1 text-xs text-zinc-400">
                        <p>Время: {formatTime(preview?.captured_at)}</p>
                        <p>Детекции: {preview?.has_detections ? "✓ есть" : "нет"}</p>
                        <p>Номер: {preview?.last_plate ?? "-"}</p>
                        <p>Решение: {preview?.last_decision ?? "-"}</p>
                    </div>
                </div>
            </section>

            {/* Zones Management Section */}
            <section className="space-y-3 border-t border-zinc-800 pt-4">
                <h3 className="text-xs uppercase tracking-widest text-zinc-500">
                    Зоны ({zones.length}/{maxZones})
                </h3>

                {zones.length > 0 ? (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                        {visibleZones.map((zone, index) => (
                            <div
                                key={`${zone.id}-${index}`}
                                className="flex items-center gap-2 rounded border border-zinc-800 bg-zinc-900/50 px-2 py-1.5"
                            >
                                {/* Toggle ON/OFF */}
                                <button
                                    type="button"
                                    className={`flex-shrink-0 w-6 h-6 rounded transition ${zone.is_enabled
                                            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                            : "bg-zinc-700/30 text-zinc-500 border border-zinc-700"
                                        }`}
                                    onClick={() =>
                                        onUpdateZone(index, (prev) => ({ ...prev, is_enabled: !prev.is_enabled }))
                                    }
                                    title={zone.is_enabled ? "Отключить" : "Включить"}
                                >
                                    {zone.is_enabled ? "✓" : ""}
                                </button>

                                {/* Zone Name */}
                                <span className="flex-1 truncate text-xs font-medium text-zinc-300">
                                    {zone.name}
                                </span>

                                {/* Delete Button */}
                                <button
                                    type="button"
                                    className="flex-shrink-0 text-red-400 hover:text-red-300 transition text-sm"
                                    onClick={() => onRemoveZone(index)}
                                    title="Удалить зону"
                                >
                                    ✕
                                </button>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-xs text-zinc-500 italic">Зоны не настроены</p>
                )}

                {/* Zone Action Buttons */}
                <div className="flex flex-col gap-2 border-t border-zinc-800 pt-3">
                    <Button onClick={onSaveZones} disabled={!zonesDirty || zonesSaving} className="w-full">
                        {zonesSaving ? (
                            <>
                                <RefreshCw className="mr-2 size-4 animate-spin" />
                                Сохраняем...
                            </>
                        ) : (
                            "Сохранить зоны"
                        )}
                    </Button>
                    <Button
                        variant="secondary"
                        onClick={onResetZones}
                        disabled={zonesSaving}
                        className="w-full"
                    >
                        Сбросить
                    </Button>
                    {zonesMessage && (
                        <p
                            className={`text-xs text-center rounded px-2 py-1 ${zonesMessage.includes("Ошибка")
                                    ? "text-red-300 bg-red-500/10"
                                    : "text-emerald-300 bg-emerald-500/10"
                                }`}
                        >
                            {zonesMessage}
                        </p>
                    )}
                </div>
            </section>

            {/* Security Section */}
            <section className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
                <p className="text-xs uppercase tracking-widest text-zinc-500">Безопасность</p>
                <p className="mt-2 text-sm text-zinc-300">
                    Система настроена на fail-closed. При неопределенности решение на открытие не принимается.
                </p>
                <div className="mt-3 flex items-center gap-2 text-amber-300">
                    <Siren className="size-4" />
                    <span className="text-xs">Предпочтение: false deny &gt; false open</span>
                </div>
            </section>
        </aside>
    )
}
