"use client"

import { useState } from "react"

import { RefreshCw, ShieldAlert, ShieldCheck, Siren, SquareDashedMousePointer } from "lucide-react"

import { Button } from "@/components/ui/button"
import { toEventImageSrc } from "@/lib/api"
import { useDashboard } from "@/hooks/use-dashboard"

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

export default function Page() {
  const { data, preview, previewImageSrc, loading, error, refreshing, isStale, syncAgeSec, refresh, runForceSync } =
    useDashboard()
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null)
  const [selectedImageError, setSelectedImageError] = useState<string | null>(null)

  const selectedEvent = data?.recent_events.find((event) => event.id === selectedEventId) ?? null
  const selectedImageSrc = selectedEventId !== null ? toEventImageSrc(selectedEventId) : null

  return (
    <main className="min-h-svh bg-gradient-to-b from-slate-950 via-zinc-900 to-zinc-950 text-zinc-100">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8">
        <header className="ops-panel flex flex-col gap-3 p-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">ALPR Control Room</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Панель шлагбаума</h1>
            <p className="mt-2 text-sm text-zinc-400">
              Мониторинг распознавания и решений в реальном времени
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => void refresh()} disabled={refreshing} variant="secondary">
              <RefreshCw className={refreshing ? "mr-2 size-4 animate-spin" : "mr-2 size-4"} />
              Обновить
            </Button>
            <Button onClick={() => void runForceSync()} disabled={refreshing}>
              <SquareDashedMousePointer className="mr-2 size-4" />
              Force Sync (1C stub)
            </Button>
          </div>
        </header>

        {isStale && (
          <section className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">
            Данные устарели. Проверьте backend API или сеть.
          </section>
        )}

        {error && (
          <section className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
            Ошибка загрузки: {error}
          </section>
        )}

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <article className="ops-card">
            <p className="ops-label">Режим открытия</p>
            <div className="mt-2 flex items-center gap-2">
              {data?.mode.dry_run_open ? (
                <>
                  <ShieldAlert className="size-5 text-amber-400" />
                  <span className="text-lg font-semibold text-amber-300">DRY-RUN</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="size-5 text-emerald-400" />
                  <span className="text-lg font-semibold text-emerald-300">ACTIVE</span>
                </>
              )}
            </div>
            <p className="mt-2 text-xs text-zinc-400">Подтверждений: {data?.mode.min_confirmations ?? "-"}</p>
          </article>

          <article className="ops-card">
            <p className="ops-label">Whitelist</p>
            <p className="mt-2 text-2xl font-semibold">{data?.whitelist.active ?? 0}</p>
            <p className="mt-1 text-xs text-zinc-400">активных • {data?.whitelist.inactive ?? 0} неактивных</p>
          </article>

          <article className="ops-card">
            <p className="ops-label">Решения за 24ч</p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-semibold text-emerald-300">{data?.kpi_24h.open ?? 0}</span>
              <span className="text-sm text-zinc-400">open</span>
            </div>
            <p className="mt-1 text-xs text-zinc-400">deny: {data?.kpi_24h.deny ?? 0}</p>
          </article>

          <article className="ops-card">
            <p className="ops-label">Средняя уверенность</p>
            <p className="mt-2 text-2xl font-semibold">{formatPercent(data?.kpi_24h.avg_confidence)}</p>
            <p className="mt-1 text-xs text-zinc-400">последние подтвержденные решения</p>
          </article>
        </section>

        <section className="grid gap-3 lg:grid-cols-3">
          <article className="ops-panel p-4 lg:col-span-2">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-300">Последние события</h2>
              <p className="text-xs text-zinc-500">{loading ? "загрузка..." : `${data?.recent_events.length ?? 0} записей`}</p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[740px] text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                    <th className="py-2 pr-3">Время</th>
                    <th className="py-2 pr-3">Номер</th>
                    <th className="py-2 pr-3">Решение</th>
                    <th className="py-2 pr-3">Причина</th>
                    <th className="py-2 pr-3">OCR</th>
                    <th className="py-2">Vote</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.recent_events.map((event) => (
                    <tr
                      key={event.id}
                      className="cursor-pointer border-b border-zinc-900/70 transition hover:bg-zinc-900/50"
                      onClick={() => {
                        setSelectedImageError(null)
                        setSelectedEventId(event.id)
                      }}
                    >
                      <td className="py-2 pr-3 text-zinc-400">{formatTime(event.occurred_at)}</td>
                      <td className="py-2 pr-3 font-semibold tracking-wide">{event.plate || event.raw_plate}</td>
                      <td className="py-2 pr-3">
                        <span
                          className={
                            event.decision === "open"
                              ? "decision-chip-open"
                              : event.decision === "deny"
                                ? "decision-chip-deny"
                                : "decision-chip-observed"
                          }
                        >
                          {event.decision}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-zinc-300">{event.reason_code}</td>
                      <td className="py-2 pr-3 text-zinc-300">{formatPercent(event.ocr_confidence)}</td>
                      <td className="py-2 text-zinc-300">
                        {event.vote_confirmations ?? "-"}
                        {event.vote_avg_confidence !== null && ` / ${formatPercent(event.vote_avg_confidence)}`}
                      </td>
                    </tr>
                  ))}
                  {!loading && !data?.recent_events.length && (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-zinc-500">
                        Пока нет событий. Запустите backend pipeline и дождитесь первых распознаваний.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <p className="mt-3 text-xs text-zinc-500">Кликните на событие, чтобы открыть сохраненный кадр распознавания.</p>
          </article>

          <article className="ops-panel p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-300">Состояние интеграций</h2>

            <div className="mt-3 rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
              <p className="text-xs uppercase tracking-widest text-zinc-500">Live Preview</p>

              <div className="mt-3 overflow-hidden rounded-md border border-zinc-800 bg-zinc-900/60">
                {previewImageSrc ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={previewImageSrc} alt="Последний кадр камеры" className="h-auto w-full object-cover" />
                ) : (
                  <div className="flex min-h-44 items-center justify-center px-3 text-center text-sm text-zinc-500">
                    Кадр еще не готов. Запустите pipeline распознавания и подождите несколько секунд.
                  </div>
                )}
              </div>

              <div className="mt-3 space-y-2 text-xs text-zinc-400">
                <p>Время кадра: {formatTime(preview?.captured_at)}</p>
                <p>Детекции: {preview?.has_detections ? "есть" : "нет"}</p>
                <p>Последний номер: {preview?.last_plate ?? "-"}</p>
                <p>Последнее решение: {preview?.last_decision ?? "-"}</p>
              </div>
            </div>

            <div className="mt-3 space-y-3 text-sm">
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
              <div className="ops-kv">
                <span>Порог confidence</span>
                <span>{formatPercent(data?.mode.min_avg_confidence)}</span>
              </div>
              <div className="ops-kv">
                <span>Окно голосования</span>
                <span>{data?.mode.voting_window_sec ?? "-"} сек</span>
              </div>
            </div>

            <div className="mt-5 rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
              <p className="text-xs uppercase tracking-widest text-zinc-500">Безопасность</p>
              <p className="mt-2 text-sm text-zinc-300">
                Система настроена на fail-closed. При неопределенности решение на открытие не принимается.
              </p>
              <div className="mt-3 flex items-center gap-2 text-amber-300">
                <Siren className="size-4" />
                <span className="text-xs">Предпочтение: false deny &gt; false open</span>
              </div>
            </div>
          </article>
        </section>
      </div>

      {selectedEventId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
          <div className="w-full max-w-5xl rounded-xl border border-zinc-800 bg-zinc-950 p-4 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Снимок события</p>
                <p className="mt-1 text-sm text-zinc-300">
                  {selectedEvent
                    ? `${formatTime(selectedEvent.occurred_at)} • ${selectedEvent.plate || selectedEvent.raw_plate} • ${selectedEvent.decision}`
                    : "Событие"}
                </p>
              </div>
              <Button variant="secondary" onClick={() => setSelectedEventId(null)}>
                Закрыть
              </Button>
            </div>

            <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/60">
              {selectedImageSrc && !selectedImageError ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={selectedImageSrc}
                  alt="Снимок события"
                  className="h-auto max-h-[75vh] w-full object-contain"
                  onError={() => setSelectedImageError("Снимок для этого события пока не найден")}
                />
              ) : (
                <div className="flex min-h-64 items-center justify-center px-4 text-center text-sm text-zinc-400">
                  {selectedImageError ?? "Снимок недоступен"}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
