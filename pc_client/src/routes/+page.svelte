<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { listen } from "@tauri-apps/api/event";

  // ── Types ──────────────────────────────────────────────────────────────────

  type CardClass = "open" | "deny";

  type Card = {
    uid: string;
    plate: string;
    label: string;
    reason: string;
    time: string;
    zone: string;
    cardClass: CardClass;
  };

  // ── State ──────────────────────────────────────────────────────────────────

  let card = $state<Card | null>(null);
  let sseConnected = $state(false);
  let sseMessage = $state("Підключення…");
  let dismissTimer: ReturnType<typeof setTimeout> | null = null;

  // ── Reason code → Ukrainian ────────────────────────────────────────────────

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

  // ── Event handler ──────────────────────────────────────────────────────────

  function onRecognition(event: Record<string, unknown>) {
    const decision = String(event.decision ?? "");
    const reason_code = String(event.reason_code ?? "");

    if (dismissTimer) { clearTimeout(dismissTimer); dismissTimer = null; }

    card = {
      uid: `${event.id}-${Date.now()}`,
      plate: String(event.plate || event.raw_plate || ""),
      label: decision === "open" ? "ВІДКРИТО" : "ВІДМОВЛЕНО",
      reason: REASONS[reason_code] ?? reason_code,
      time: fmtTime(String(event.occurred_at ?? "")),
      zone: String(event.zone_name ?? ""),
      cardClass: decision === "open" ? "open" : "deny",
    };

    dismissTimer = setTimeout(() => { card = null; }, 30_000);
  }

  // ── Listeners ──────────────────────────────────────────────────────────────

  let unlistenEvent: (() => void) | null = null;
  let unlistenStatus: (() => void) | null = null;

  onMount(async () => {
    unlistenEvent = await listen<Record<string, unknown>>("recognition-event", (e) => {
      onRecognition(e.payload);
    });
    unlistenStatus = await listen<{ connected: boolean; message: string }>("sse-status", (e) => {
      sseConnected = e.payload.connected;
      sseMessage = e.payload.message;
    });
  });

  onDestroy(() => {
    unlistenEvent?.();
    unlistenStatus?.();
    if (dismissTimer) clearTimeout(dismissTimer);
  });
</script>

<div class="wrapper">
  <!-- ── Status bar (always visible) ── -->
  <div class="statusbar">
    <span class="dot" class:ok={sseConnected}></span>
    <span class="statusbar-text">
      {sseConnected ? "ALPR Монітор — очікування" : sseMessage}
    </span>
  </div>

  <!-- ── Event card (shown 30 s after last event) ── -->
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
</div>

<style>
  :global(*) { box-sizing: border-box; margin: 0; padding: 0; }

  :global(html), :global(body) {
    background: transparent !important;
    overflow: hidden;
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
  }

  .wrapper {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 6px;
    width: 340px;
  }

  /* ── Status bar ── */
  .statusbar {
    display: flex;
    align-items: center;
    gap: 7px;
    background: rgba(13, 17, 27, 0.92);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 8px;
    padding: 7px 12px;
    backdrop-filter: blur(12px);
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    background: #475569;
    transition: background 0.4s;
  }
  .dot.ok { background: #22c55e; }

  .statusbar-text {
    font-size: 11px;
    color: #64748b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* ── Card ── */
  .card {
    display: flex;
    border-radius: 10px;
    background: rgba(13, 17, 27, 0.96);
    backdrop-filter: blur(12px);
    box-shadow: 0 6px 32px rgba(0,0,0,0.6), 0 1px 0 rgba(255,255,255,0.04) inset;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.07);
  }

  .card.open { animation: slide-in 0.15s ease-out, blink-green 0.9s ease-out 0.15s; }
  .card.deny { animation: slide-in 0.15s ease-out, blink-red   0.9s ease-out 0.15s; }

  @keyframes slide-in {
    from { opacity: 0; transform: translateX(20px); }
    to   { opacity: 1; transform: translateX(0); }
  }

  @keyframes blink-green {
    0%   { background: rgba(13, 17, 27, 0.96); }
    20%  { background: rgba(34, 197, 94, 0.45); }
    40%  { background: rgba(13, 17, 27, 0.96); }
    65%  { background: rgba(34, 197, 94, 0.30); }
    100% { background: rgba(13, 17, 27, 0.96); }
  }

  @keyframes blink-red {
    0%   { background: rgba(13, 17, 27, 0.96); }
    20%  { background: rgba(239, 68, 68, 0.45); }
    40%  { background: rgba(13, 17, 27, 0.96); }
    65%  { background: rgba(239, 68, 68, 0.30); }
    100% { background: rgba(13, 17, 27, 0.96); }
  }

  /* ── Accent bar ── */
  .accent-bar { width: 5px; flex-shrink: 0; }
  .card.open .accent-bar { background: #22c55e; }
  .card.deny .accent-bar { background: #ef4444; }

  /* ── Body ── */
  .body { padding: 10px 13px 9px; flex: 1; min-width: 0; }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }

  .label { font-size: 10px; font-weight: 700; letter-spacing: 0.14em; }
  .card.open .label { color: #4ade80; }
  .card.deny .label { color: #f87171; }

  .time { font-size: 11px; color: #475569; font-variant-numeric: tabular-nums; }

  .plate {
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: 0.1em;
    font-family: "Consolas", "Courier New", monospace;
    margin-bottom: 4px;
    line-height: 1.1;
  }

  .meta { font-size: 11px; color: #94a3b8; line-height: 1.4; }
  .zone { color: #475569; margin-top: 2px; }
</style>
