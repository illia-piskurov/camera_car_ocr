"use client"

import { useEffect, useState } from "react"

import { RefreshCw, SquareDashedMousePointer } from "lucide-react"

import { Button } from "@/components/ui/button"
import { PreviewWithZones } from "@/components/PreviewWithZones"
import { DashboardSidebar } from "@/components/DashboardSidebar"
import { saveZones, toEventImageSrc } from "@/lib/api"
import { useDashboard } from "@/hooks/use-dashboard"
import type { DetectionZone } from "@/lib/types"

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

export default function Page() {
  const { data, preview, previewImageSrc, loading, error, refreshing, isStale, syncAgeSec, refresh, runForceSync } =
    useDashboard()
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null)
  const [selectedImageError, setSelectedImageError] = useState<string | null>(null)
  const [zoneDraft, setZoneDraft] = useState<DetectionZone[]>([])
  const [zonesDirty, setZonesDirty] = useState(false)
  const [zonesSaving, setZonesSaving] = useState(false)
  const [zonesMessage, setZonesMessage] = useState<string | null>(null)
  const [editMode, setEditMode] = useState(false)

  useEffect(() => {
    if (!zonesDirty && preview?.zones) {
      setZoneDraft(preview.zones)
    }
  }, [preview, zonesDirty])

  const selectedEvent = data?.recent_events.find((event) => event.id === selectedEventId) ?? null
  const selectedImageSrc = selectedEventId !== null ? toEventImageSrc(selectedEventId) : null
  const maxZones = preview?.max_zones ?? 3

  async function handleSaveZones() {
    setZonesSaving(true)
    setZonesMessage(null)
    try {
      await saveZones(zoneDraft)
      setZonesDirty(false)
      setZonesMessage("Зоны сохранены")
      setEditMode(false)
      await refresh()
    } catch (saveError) {
      setZonesMessage(saveError instanceof Error ? saveError.message : "Ошибка сохранения зон")
    } finally {
      setZonesSaving(false)
    }
  }

  function handleResetZones() {
    setZoneDraft(preview?.zones ?? [])
    setZonesDirty(false)
    setZonesMessage(null)
    setEditMode(false)
  }

  function handleUpdateZone(index: number, updater: (zone: DetectionZone) => DetectionZone) {
    const updated = zoneDraft.map((zone, zoneIndex) => (zoneIndex === index ? updater(zone) : zone))
    setZoneDraft(updated)
    setZonesDirty(true)
    setZonesMessage(null)
  }

  function handleRemoveZone(index: number) {
    const updated = zoneDraft
      .filter((_, zoneIndex) => zoneIndex !== index)
      .map((zone, zoneIndex) => ({
        ...zone,
        sort_order: zoneIndex,
        name: zone.name || `Zone ${zoneIndex + 1}`,
      }))
    setZoneDraft(updated)
    setZonesDirty(true)
    setZonesMessage(null)
  }

  return (
    <main className="min-h-svh bg-gradient-to-b from-slate-950 via-zinc-900 to-zinc-950 text-zinc-100">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8">
        {/* Header */}
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

        {/* Alerts */}
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

        {/* Main Layout: Left (Events + Preview) + Right (Sidebar) */}
        <section className="grid gap-4 lg:grid-cols-[1fr_0.65fr]">
          {/* Left Column: Events Table + Live Preview */}
          <article className="ops-panel p-4 space-y-6">
            {/* Events Table */}
            <div>
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
                      <th className="py-2 pr-3">Зона</th>
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
                        <td className="py-2 pr-3 text-zinc-300">{event.zone_name ?? "full"}</td>
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
                        <td colSpan={7} className="py-8 text-center text-zinc-500">
                          Пока нет событий. Запустите backend pipeline и дождитесь первых распознаваний.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <p className="mt-3 text-xs text-zinc-500">Кликните на событие, чтобы открыть сохраненный кадр распознавания.</p>
            </div>

            {/* Live Preview with Zones */}
            <div className="border-t border-zinc-800 pt-6">
              <PreviewWithZones
                imageSrc={previewImageSrc}
                zones={zoneDraft}
                maxZones={maxZones}
                editMode={editMode}
                onChangeZones={(zones) => {
                  setZoneDraft(zones)
                  setZonesDirty(true)
                  setZonesMessage(null)
                }}
                onEditModeToggle={() => setEditMode(!editMode)}
              />
            </div>
          </article>

          {/* Right Column: Dashboard Sidebar */}
          <aside>
            <DashboardSidebar
              data={data}
              preview={preview}
              zones={zoneDraft}
              maxZones={maxZones}
              zonesDirty={zonesDirty}
              zonesSaving={zonesSaving}
              zonesMessage={zonesMessage}
              onSaveZones={() => void handleSaveZones()}
              onResetZones={handleResetZones}
              onUpdateZone={handleUpdateZone}
              onRemoveZone={handleRemoveZone}
              syncAgeSec={syncAgeSec}
            />
          </aside>
        </section>
      </div>

      {/* Event Modal */}
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
