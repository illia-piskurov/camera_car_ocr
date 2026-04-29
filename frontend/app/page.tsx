"use client"

import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { ControlRoomHeader } from "@/components/ControlRoomHeader"
import { ConfirmationDialog } from "@/components/ConfirmationDialog"
import { PreviewWithZones } from "@/components/PreviewWithZones"
import { ZonesPanel } from "@/components/ZonesPanel"
import { EventsTable } from "@/components/EventsTable"
import { OnboardingPanel } from "@/components/OnboardingPanel"
import { deleteCamera, saveZones, saveCameraZones, toEventImageSrc, updateCamera } from "@/lib/api"
import { useDashboard } from "@/hooks/use-dashboard"
import type { Camera, DetectionZone } from "@/lib/types"

function formatTime(value: string | null | undefined) {
  if (!value) {
    return "-"
  }
  return new Date(value).toLocaleString("en-US")
}

export default function Page() {
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null)
  const [cameraFormMode, setCameraFormMode] = useState<"create" | "edit" | null>(null)
  const [cameraFormCamera, setCameraFormCamera] = useState<Camera | null>(null)
  const [cameraToDelete, setCameraToDelete] = useState<Camera | null>(null)
  const [cameraDeleteBusy, setCameraDeleteBusy] = useState(false)
  const [cameraDeleteError, setCameraDeleteError] = useState<string | null>(null)
  const [cameraStateError, setCameraStateError] = useState<string | null>(null)
  const { data, preview, previewImageSrc, cameras, loading, error, refreshing, isStale, syncAgeSec, refresh, runForceSync } =
    useDashboard(selectedCameraId)
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null)
  const [selectedImageError, setSelectedImageError] = useState<string | null>(null)
  const [zoneDraft, setZoneDraft] = useState<DetectionZone[]>([])
  const [zonesDirty, setZonesDirty] = useState(false)
  const [zonesSaving, setZonesSaving] = useState(false)
  const [zonesMessage, setZonesMessage] = useState<string | null>(null)

  // Set default camera on first load
  useEffect(() => {
    if (cameras.length > 0 && selectedCameraId === null) {
      const activeCamera = cameras.find((c) => c.is_active)
      setSelectedCameraId(activeCamera?.id ?? cameras[0]?.id ?? null)
    }
  }, [cameras, selectedCameraId])

  useEffect(() => {
    if (cameraFormMode === "edit" && cameraFormCamera) {
      const nextCamera = cameras.find((camera) => camera.id === cameraFormCamera.id) ?? null
      if (nextCamera && nextCamera !== cameraFormCamera) {
        setCameraFormCamera(nextCamera)
      }
    }
  }, [cameraFormCamera, cameraFormMode, cameras])

  useEffect(() => {
    if (!zonesDirty && preview?.zones) {
      setZoneDraft(preview.zones)
    }
  }, [preview, zonesDirty])

  const selectedEvent = data?.recent_events.find((event) => event.id === selectedEventId) ?? null
  const selectedImageSrc = selectedEventId !== null ? toEventImageSrc(selectedEventId) : null
  const maxZones = preview?.max_zones ?? 2
  const selectedCamera = cameras.find((camera) => camera.id === selectedCameraId) ?? null

  async function handleCameraSaved(camera: Camera) {
    setCameraFormMode(null)
    setCameraFormCamera(null)
    setSelectedCameraId(camera.id)
    if (selectedCameraId === camera.id) {
      await refresh()
    }
  }

  function handleOpenCreateCamera() {
    setCameraFormCamera(null)
    setCameraFormMode("create")
  }

  function handleOpenEditCamera(camera: Camera) {
    setSelectedCameraId(camera.id)
    setCameraFormCamera(camera)
    setCameraFormMode("edit")
  }

  function handleOpenDeleteCamera(camera: Camera) {
    setCameraDeleteError(null)
    setCameraToDelete(camera)
  }

  async function handleToggleSelectedCameraActive(nextActive: boolean) {
    const camera = cameras.find((item) => item.id === selectedCameraId)
    if (!camera) {
      return
    }

    setCameraStateError(null)

    try {
      await updateCamera(camera.id, { is_active: nextActive })
      await refresh()
    } catch (toggleError) {
      setCameraStateError(toggleError instanceof Error ? toggleError.message : "Failed to update camera state")
    }
  }

  async function handleConfirmDeleteCamera() {
    if (!cameraToDelete) {
      return
    }

    setCameraDeleteBusy(true)
    setCameraDeleteError(null)

    const deletedCameraId = cameraToDelete.id
    const remainingCameras = cameras.filter((camera) => camera.id !== deletedCameraId)
    const fallbackCamera = remainingCameras.find((camera) => camera.is_active) ?? remainingCameras[0] ?? null

    try {
      await deleteCamera(deletedCameraId)
      setCameraToDelete(null)
      setCameraFormMode(null)
      setCameraFormCamera(null)
      if (selectedCameraId === deletedCameraId) {
        setSelectedCameraId(fallbackCamera?.id ?? null)
      } else {
        await refresh()
      }
    } catch (deleteError) {
      setCameraDeleteError(deleteError instanceof Error ? deleteError.message : "Failed to delete camera")
    } finally {
      setCameraDeleteBusy(false)
    }
  }

  // Show onboarding if no cameras or when user explicitly opens add/edit camera flow.
  if ((!loading && cameras.length === 0) || cameraFormMode !== null) {
    const formMode = cameraFormMode ?? "create"
    return (
      <OnboardingPanel
        mode={formMode}
        camera={cameraFormCamera}
        onCameraSaved={(camera) => {
          void handleCameraSaved(camera)
        }}
        isFirstCameraFlow={cameras.length === 0 && formMode === "create"}
        onCancel={cameras.length > 0 ? () => {
          setCameraFormMode(null)
          setCameraFormCamera(null)
        } : undefined}
      />
    )
  }

  async function handleSaveZones() {
    setZonesSaving(true)
    setZonesMessage(null)
    try {
      if (selectedCameraId) {
        await saveCameraZones(selectedCameraId, zoneDraft)
      } else {
        await saveZones(zoneDraft)
      }
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
      }))
    setZoneDraft(updated)
    setZonesDirty(true)
    setZonesMessage(null)
  }


  return (
    <main className="min-h-svh bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-slate-100">
      <ControlRoomHeader
        cameras={cameras}
        selectedCameraId={selectedCameraId}
        onSelectCamera={setSelectedCameraId}
        onAddCamera={handleOpenCreateCamera}
        onEditCamera={handleOpenEditCamera}
        onDeleteCamera={handleOpenDeleteCamera}
        syncAgeSec={syncAgeSec}
        onRefresh={() => void refresh()}
        onForceSync={() => void runForceSync()}
        refreshing={refreshing}
      />

      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8">

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

        {cameraStateError && (
          <section className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">
            Camera update error: {cameraStateError}
          </section>
        )}

        {/* Row 2: Preview (left 2/3) + Zones Panel (right 1/3) */}
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
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
              headerAction={
                selectedCamera ? (
                  <button
                    type="button"
                    role="switch"
                    aria-checked={selectedCamera.is_active}
                    aria-label={selectedCamera.is_active ? `Deactivate ${selectedCamera.name}` : `Activate ${selectedCamera.name}`}
                    onClick={() => void handleToggleSelectedCameraActive(!selectedCamera.is_active)}
                    className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition ${selectedCamera.is_active
                      ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-200 hover:bg-emerald-500/25"
                      : "border-slate-600 bg-slate-800/80 text-slate-300 hover:bg-slate-700"
                      }`}
                  >
                    <span className={`size-2 rounded-full ${selectedCamera.is_active ? "bg-emerald-400" : "bg-slate-500"}`} />
                    {selectedCamera.is_active ? "Active" : "Inactive"}
                  </button>
                ) : null
              }
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
          <div className="w-full max-w-5xl rounded-xl border border-slate-700/90 bg-slate-900 p-4 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Event Snapshot</p>
                <p className="mt-1 text-sm text-slate-200">
                  {selectedEvent
                    ? `${formatTime(selectedEvent.occurred_at)} • ${selectedEvent.plate || selectedEvent.raw_plate} • ${selectedEvent.decision}`
                    : "Event"}
                </p>
              </div>
              <Button variant="secondary" onClick={() => setSelectedEventId(null)}>
                Close
              </Button>
            </div>

            <div className="overflow-hidden rounded-lg border border-slate-700/80 bg-slate-800/60">
              {selectedImageSrc && !selectedImageError ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={selectedImageSrc}
                  alt="Event snapshot"
                  className="h-auto max-h-[75vh] w-full object-contain"
                  onError={() => setSelectedImageError("Snapshot for this event has not been found yet")}
                />
              ) : (
                <div className="flex min-h-64 items-center justify-center px-4 text-center text-sm text-slate-300">
                  {selectedImageError ?? "Snapshot unavailable"}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <ConfirmationDialog
        open={cameraToDelete !== null}
        title={cameraToDelete ? `Delete ${cameraToDelete.name}?` : "Delete camera?"}
        description={cameraToDelete ? "This will permanently remove the camera, its zones, and its recognition events." : "This action cannot be undone."}
        confirmLabel="Delete camera"
        busy={cameraDeleteBusy}
        error={cameraDeleteError}
        onConfirm={() => void handleConfirmDeleteCamera()}
        onCancel={() => {
          setCameraToDelete(null)
          setCameraDeleteError(null)
        }}
      />
    </main>
  )
}
