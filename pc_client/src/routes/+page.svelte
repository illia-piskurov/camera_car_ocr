<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { listen } from "@tauri-apps/api/event";
  import { getCurrentWindow } from "@tauri-apps/api/window";

  const appWindow = getCurrentWindow();

  // ── Types ──────────────────────────────────────────────────────────────────

  type CardClass = "open" | "deny" | "skip";

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

  let cards = $state<Card[]>([]);
  const timers = new Map<string, ReturnType<typeof setTimeout>>();

  // ── Reason code → Ukrainian ────────────────────────────────────────────────

  const REASONS: Record<string, string> = {
    open_approved:          "Номер знайдено в базі дозволених",
    open_fuzzy_edit:        "Номер розпізнано з виправленням",
    not_whitelisted:        "Номер відсутній у базі дозволених",
    cross_camera_suppressed:"Шлагбаум вже відкрито по сусідній камері",
    raw_detection:          "Розпізнавання без рішення",
  };

  function classify(decision: string, reason: string): { cls: CardClass; label: string } {
    if (decision === "open") return { cls: "open", label: "ВІДКРИТО" };
    if (reason === "not_whitelisted") return { cls: "deny", label: "ВІДМОВЛЕНО" };
    return { cls: "skip", label: "ПРОПУЩЕНО" };
  }

  function fmtTime(iso: string): string {
    return new Date(iso).toLocaleTimeString("uk-UA", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  // ── Card lifecycle ─────────────────────────────────────────────────────────

  async function addCard(event: Record<string, unknown>) {
    const decision = String(event.decision ?? "");
    const reason_code = String(event.reason_code ?? "");

    const { cls, label } = classify(decision, reason_code);
    const uid = `${event.id}-${Date.now()}`;

    const card: Card = {
      uid,
      plate: String(event.plate || event.raw_plate || ""),
      label,
      reason: REASONS[reason_code] ?? reason_code,
      time: fmtTime(String(event.occurred_at ?? "")),
      zone: String(event.zone_name ?? ""),
      cardClass: cls,
    };

    // Max 3 visible — drop oldest if overflow
    const next = [...cards, card];
    if (next.length > 3) {
      const dropped = next.shift()!;
      clearTimeout(timers.get(dropped.uid));
      timers.delete(dropped.uid);
    }
    cards = next;

    if (cards.length === 1) {
      await appWindow.show();
    }

    timers.set(uid, setTimeout(() => void removeCard(uid), 10_000));
  }

  async function removeCard(uid: string) {
    const t = timers.get(uid);
    if (t !== undefined) { clearTimeout(t); timers.delete(uid); }
    cards = cards.filter((c) => c.uid !== uid);
    if (cards.length === 0) {
      await appWindow.hide();
    }
  }

  // ── Tauri event listeners ──────────────────────────────────────────────────

  let unlistenEvent: (() => void) | null = null;

  onMount(async () => {
    unlistenEvent = await listen<Record<string, unknown>>("recognition-event", (e) => {
      void addCard(e.payload);
    });
  });

  onDestroy(() => {
    unlistenEvent?.();
    timers.forEach((t) => clearTimeout(t));
  });
</script>

<div class="stack">
  {#each cards as card (card.uid)}
    <div class="card {card.cardClass}">
      <div class="accent-bar"></div>
      <div class="body">
        <div class="header">
          <span class="label">{card.label}</span>
          <span class="time">{card.time}</span>
        </div>
        <div class="plate">{card.plate}</div>
        <div class="reason">{card.reason}</div>
        {#if card.zone}
          <div class="zone">{card.zone}</div>
        {/if}
      </div>
    </div>
  {/each}
</div>

<style>
  :global(*) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(html),
  :global(body) {
    background: transparent !important;
    overflow: hidden;
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
  }

  .stack {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px;
    width: 390px;
  }

  /* ── Card ── */
  .card {
    display: flex;
    border-radius: 10px;
    background: rgba(13, 17, 27, 0.96);
    backdrop-filter: blur(12px);
    box-shadow: 0 6px 32px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(255,255,255,0.04) inset;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.07);
    animation: slide-in 0.2s ease-out;
  }

  @keyframes slide-in {
    from { opacity: 0; transform: translateX(24px); }
    to   { opacity: 1; transform: translateX(0); }
  }

  /* ── Accent bar (left stripe) ── */
  .accent-bar {
    width: 5px;
    flex-shrink: 0;
  }
  .card.open  .accent-bar { background: #22c55e; }
  .card.deny  .accent-bar { background: #ef4444; }
  .card.skip  .accent-bar { background: #eab308; }

  /* ── Content ── */
  .body {
    padding: 12px 14px 10px;
    flex: 1;
    min-width: 0;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 5px;
  }

  .label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.14em;
  }
  .card.open .label { color: #4ade80; }
  .card.deny .label { color: #f87171; }
  .card.skip .label { color: #facc15; }

  .time {
    font-size: 11px;
    color: #475569;
    font-variant-numeric: tabular-nums;
  }

  .plate {
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: 0.1em;
    font-family: "Consolas", "Courier New", monospace;
    margin-bottom: 5px;
    line-height: 1.1;
  }

  .reason {
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.4;
  }

  .zone {
    font-size: 11px;
    color: #475569;
    margin-top: 3px;
  }
</style>
