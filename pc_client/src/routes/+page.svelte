<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { listen } from "@tauri-apps/api/event";
  import { invoke } from "@tauri-apps/api/core";

  // ── Types ──────────────────────────────────────────────────────────────────

  type CardClass = "open" | "deny";
  type SizeKey   = "small" | "medium" | "large";

  type Card = {
    uid: string; plate: string; label: string;
    reason: string; time: string; zone: string; cardClass: CardClass;
  };

  // Font size per window size (px). Dimensions live in Rust — compact_dims / expanded_dims.
  const FS: Record<SizeKey, number> = { small: 11.5, medium: 14, large: 17.5 };

  // ── State ──────────────────────────────────────────────────────────────────

  let card           = $state<Card | null>(null);
  let sseConnected   = $state(false);
  let fontSize       = $state(14);
  let sizeKey        = $state<SizeKey>("medium");
  let displayTimeSec = $state(30);
  let dismissTimer: ReturnType<typeof setTimeout> | null = null;

  // ── Reason codes ───────────────────────────────────────────────────────────

  const REASONS: Record<string, string> = {
    open_approved:           "Номер знайдено в базі дозволених",
    open_fuzzy_edit:         "Номер розпізнано з виправленням",
    not_whitelisted:         "Номер відсутній у базі дозволених",
    cross_camera_suppressed: "Шлагбаум вже відкрито по сусідній камері",
  };

  function fmtTime(iso: string): string {
    return new Date(iso).toLocaleTimeString("uk-UA", {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  }

  // ── Window resize — delegated to Rust to avoid WebView2 DPI issues ─────────

  function resizeWindow(hasCard: boolean): void {
    invoke("resize_alert_window", { hasCard, sizeKey }).catch(
      (e) => console.error("resize_alert_window failed:", e)
    );
  }

  // ── Event handler ──────────────────────────────────────────────────────────

  function onRecognition(event: Record<string, unknown>) {
    const decision    = String(event.decision ?? "");
    const reason_code = String(event.reason_code ?? "");

    if (dismissTimer) { clearTimeout(dismissTimer); dismissTimer = null; }

    card = {
      uid:       `${event.id}-${Date.now()}`,
      plate:     String(event.plate || event.raw_plate || ""),
      label:     decision === "open" ? "ВІДКРИТО" : "ВІДМОВЛЕНО",
      reason:    REASONS[reason_code] ?? reason_code,
      time:      fmtTime(String(event.occurred_at ?? "")),
      zone:      String(event.zone_name ?? ""),
      cardClass: decision === "open" ? "open" : "deny",
    };

    resizeWindow(true);
    dismissTimer = setTimeout(() => {
      card = null;
      resizeWindow(false);
    }, displayTimeSec * 1000);
  }

  // ── Init ───────────────────────────────────────────────────────────────────

  let unlistenEvent:  (() => void) | null = null;
  let unlistenStatus: (() => void) | null = null;

  onMount(async () => {
    unlistenEvent = await listen<Record<string, unknown>>("recognition-event", (e) => {
      onRecognition(e.payload);
    });
    unlistenStatus = await listen<{ connected: boolean; message: string }>("sse-status", (e) => {
      sseConnected = e.payload.connected;
    });

    // Sync initial SSE state (event may fire before listener is ready)
    sseConnected = await invoke<boolean>("get_sse_status");

    // Load saved settings
    displayTimeSec = await invoke<number>("get_display_time");
    const savedSize = await invoke<string>("get_window_size") as SizeKey;
    sizeKey  = savedSize;
    fontSize = FS[savedSize] ?? 14;

    // Shrink window to compact (status-bar only) on startup
    resizeWindow(false);
  });

  onDestroy(() => {
    unlistenEvent?.();
    unlistenStatus?.();
    if (dismissTimer) clearTimeout(dismissTimer);
  });
</script>

<div class="wrapper" style="font-size: {fontSize}px">
  {#if card}
    {#key card.uid}
      <div class="card {card.cardClass}">
        <div class="accent-bar"></div>
        <div class="body">
          <div class="header">
            <span class="label">{card.label}</span>
            <span class="time">{card.time}</span>
          </div>
          <div class="plate">{card.plate}</div>
          <div class="meta">{card.reason}</div>
          {#if card.zone}
            <div class="meta zone">{card.zone}</div>
          {/if}
        </div>
      </div>
    {/key}
  {/if}

  <div class="statusbar">
    <span class="dot" class:ok={sseConnected}></span>
    <span class="statusbar-text">
      {sseConnected ? "Система розпізнавання працює" : "З'єднання відсутнє"}
    </span>
  </div>
</div>

<style>
  :global(*) { box-sizing: border-box; margin: 0; padding: 0; }

  :global(html), :global(body) {
    background: transparent !important;
    overflow: hidden;
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
    height: 100%;
  }

  .wrapper {
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    height: 100vh;
    padding: 0.4em;
    gap: 0.4em;
  }

  /* ── Status bar ── */
  .statusbar {
    display: flex;
    align-items: center;
    gap: 0.5em;
    background: rgba(13, 17, 27, 0.92);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 0.6em;
    padding: 0.5em 0.85em;
    backdrop-filter: blur(12px);
    flex-shrink: 0;
  }

  .dot {
    width: 0.57em;
    height: 0.57em;
    border-radius: 50%;
    flex-shrink: 0;
    background: #ef4444;
    transition: background 0.4s;
  }
  .dot.ok { background: #22c55e; }

  .statusbar-text {
    font-size: 0.79em;
    color: #94a3b8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* ── Card ── */
  .card {
    display: flex;
    border-radius: 0.72em;
    background: rgba(13, 17, 27, 0.96);
    backdrop-filter: blur(12px);
    box-shadow: 0 6px 32px rgba(0,0,0,0.6), 0 1px 0 rgba(255,255,255,0.04) inset;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.07);
    flex-shrink: 0;
  }

  .card.open { animation: slide-in 0.15s ease-out, blink-green 0.9s ease-out 0.15s; }
  .card.deny { animation: slide-in 0.15s ease-out, blink-red   0.9s ease-out 0.15s; }

  @keyframes slide-in {
    from { opacity: 0; transform: translateX(1.5em); }
    to   { opacity: 1; transform: translateX(0); }
  }
  @keyframes blink-green {
    0%   { background: rgba(13,17,27,0.96); }
    20%  { background: rgba(34,197,94,0.45); }
    40%  { background: rgba(13,17,27,0.96); }
    65%  { background: rgba(34,197,94,0.30); }
    100% { background: rgba(13,17,27,0.96); }
  }
  @keyframes blink-red {
    0%   { background: rgba(13,17,27,0.96); }
    20%  { background: rgba(239,68,68,0.45); }
    40%  { background: rgba(13,17,27,0.96); }
    65%  { background: rgba(239,68,68,0.30); }
    100% { background: rgba(13,17,27,0.96); }
  }

  .accent-bar { width: 0.36em; flex-shrink: 0; }
  .card.open .accent-bar { background: #22c55e; }
  .card.deny .accent-bar { background: #ef4444; }

  .body { padding: 0.72em 0.93em 0.65em; flex: 1; min-width: 0; }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.29em;
  }

  .label { font-size: 0.72em; font-weight: 700; letter-spacing: 0.14em; }
  .card.open .label { color: #4ade80; }
  .card.deny .label { color: #f87171; }

  .time { font-size: 0.79em; color: #475569; font-variant-numeric: tabular-nums; }

  .plate {
    font-size: 1.57em;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: 0.1em;
    font-family: "Consolas", "Courier New", monospace;
    margin-bottom: 0.28em;
    line-height: 1.1;
  }

  .meta { font-size: 0.79em; color: #94a3b8; line-height: 1.4; }
  .zone { color: #475569; margin-top: 0.15em; }
</style>
