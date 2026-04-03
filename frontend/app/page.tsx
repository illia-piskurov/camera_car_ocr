"use client"

import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { ControlRoomHeader } from "@/components/ControlRoomHeader"
import { PreviewWithZones } from "@/components/PreviewWithZones"
import { ZonesPanel } from "@/components/ZonesPanel"
import { EventsTable } from "@/components/EventsTable"
import { saveZones, toEventImageSrc } from "@/lib/api"
import { useDashboard } from "@/hooks/use-dashboard"
import type { DetectionZone } from "@/lib/types"

function formatTime(value: string | null | undefined) {
  if (!value) {
    return "-"
  }
  return new Date(value).toLocaleString("en-US")
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
      setZonesMessage("Zones saved")
      await refresh()
    } catch (saveError) {
      setZonesMessage(saveError instanceof Error ? saveError.message : "Failed to save zones")
    } finally {
      setZonesSaving(false)
    }
  }

  function handleResetZones() {
    setZoneDraft(preview?.zones ?? [])
    setZonesDirty(false)
    setZonesMessage(null)
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
        {/* Row 1: Header */}
        <ControlRoomHeader
          syncAgeSec={syncAgeSec}
          onRefresh={() => void refresh()}
          onForceSync={() => void runForceSync()}
          refreshing={refreshing}
        />

        {/* Alerts */}
        {isStale && (
          <section className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">
            Data is stale. Check the backend API or the network.
          </section>
        )}

        {error && (
          <section className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
            Load error: {error}
          </section>
        )}

        {/* Row 2: Preview (left 2/3) + Zones Panel (right 1/3) */}
        <section className="grid gap-4 grid-cols-[2fr_1fr]">
          {/* Left: Preview */}
          <div className="ops-panel p-4">
            <PreviewWithZones
              imageSrc={previewImageSrc}
              zones={zoneDraft}
              onChangeZones={(zones) => {
                setZoneDraft(zones)
                setZonesDirty(true)
                setZonesMessage(null)
              }}
            />
          </div>

          {/* Right: Zones Panel */}
          <div className="ops-panel p-4">
            <ZonesPanel
              zones={zoneDraft}
              maxZones={maxZones}
              zonesDirty={zonesDirty}
              zonesSaving={zonesSaving}
              zonesMessage={zonesMessage}
              onChangeZones={(zones) => {
                setZoneDraft(zones)
                setZonesDirty(true)
                setZonesMessage(null)
              }}
              onSaveZones={() => void handleSaveZones()}
              onResetZones={handleResetZones}
              onUpdateZone={handleUpdateZone}
              onRemoveZone={handleRemoveZone}
            />
          </div>
        </section>

        {/* Row 3: Events Table */}
        <div className="ops-panel p-4">
          <EventsTable
            events={data?.recent_events}
            loading={loading}
            onEventSelect={(eventId) => {
              setSelectedImageError(null)
              setSelectedEventId(eventId)
            }}
          />
        </div>
      </div>

      {/* Event Modal */}
      {selectedEventId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
          <div className="w-full max-w-5xl rounded-xl border border-zinc-800 bg-zinc-950 p-4 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Event Snapshot</p>
                <p className="mt-1 text-sm text-zinc-300">
                  {selectedEvent
                    ? `${formatTime(selectedEvent.occurred_at)} • ${selectedEvent.plate || selectedEvent.raw_plate} • ${selectedEvent.decision}`
                    : "Event"}
                </p>
              </div>
              <Button variant="secondary" onClick={() => setSelectedEventId(null)}>
                Close
              </Button>
            </div>

            <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/60">
              {selectedImageSrc && !selectedImageError ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={selectedImageSrc}
                  alt="Event snapshot"
                  className="h-auto max-h-[75vh] w-full object-contain"
                  onError={() => setSelectedImageError("Snapshot for this event has not been found yet")}
                />
              ) : (
                <div className="flex min-h-64 items-center justify-center px-4 text-center text-sm text-zinc-400">
                  {selectedImageError ?? "Snapshot unavailable"}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
