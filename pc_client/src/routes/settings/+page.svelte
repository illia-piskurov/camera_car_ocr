<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";

  let url = $state("http://localhost:8000");
  let saved = $state(false);
  let testing = $state(false);
  let testStatus = $state<{ ok: boolean; text: string } | null>(null);

  onMount(async () => {
    url = await invoke<string>("get_settings");
  });

  async function save() {
    await invoke("save_settings", { url });
    saved = true;
    setTimeout(() => (saved = false), 2000);
  }

  async function test() {
    testing = true;
    testStatus = null;
    try {
      const r = await fetch(`${url}/health`);
      const data = (await r.json()) as { status?: string };
      const ok = data.status === "ok";
      testStatus = { ok, text: ok ? "Підключено успішно" : `Статус: ${data.status}` };
    } catch (e) {
      testStatus = { ok: false, text: `Не вдалося підключитись` };
    } finally {
      testing = false;
    }
  }
</script>

<div class="wrap">
  <h1>Налаштування</h1>

  <label for="url-input">URL бекенду</label>
  <input id="url-input" type="text" bind:value={url} placeholder="http://192.168.100.112:8000" />

  {#if testStatus}
    <div class="status" class:ok={testStatus.ok} class:fail={!testStatus.ok}>
      {testStatus.text}
    </div>
  {/if}

  <div class="actions">
    <button class="btn secondary" onclick={test} disabled={testing}>
      {testing ? "Перевірка…" : "Перевірити з'єднання"}
    </button>
    <button class="btn primary" class:flash={saved} onclick={save}>
      {saved ? "Збережено ✓" : "Зберегти"}
    </button>
  </div>

  <p class="note">Нове значення застосується при наступному підключенні до сервера.</p>
</div>

<style>
  :global(*) { box-sizing: border-box; margin: 0; padding: 0; }

  :global(html), :global(body) {
    background: #0f1219;
    color: #e2e8f0;
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 14px;
    -webkit-font-smoothing: antialiased;
  }

  .wrap {
    padding: 24px 28px;
  }

  h1 {
    font-size: 15px;
    font-weight: 600;
    color: #cbd5e1;
    letter-spacing: 0.04em;
    margin-bottom: 20px;
  }

  label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #64748b;
    margin-bottom: 6px;
  }

  input {
    width: 100%;
    padding: 9px 12px;
    background: #1e2535;
    border: 1px solid #2d3748;
    border-radius: 7px;
    color: #f1f5f9;
    font-size: 13px;
    outline: none;
    margin-bottom: 14px;
    transition: border-color 0.15s;
  }
  input:focus { border-color: #3b82f6; }

  .status {
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 12px;
    margin-bottom: 14px;
  }
  .status.ok   { background: rgba(34,197,94,0.12);  color: #4ade80; border: 1px solid rgba(34,197,94,0.25); }
  .status.fail { background: rgba(239,68,68,0.12);  color: #f87171; border: 1px solid rgba(239,68,68,0.25); }

  .actions {
    display: flex;
    gap: 10px;
    margin-bottom: 14px;
  }

  .btn {
    padding: 8px 18px;
    border-radius: 7px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: background 0.15s, opacity 0.15s;
  }
  .btn:disabled { opacity: 0.45; cursor: default; }

  .primary { background: #3b82f6; color: #fff; }
  .primary:not(:disabled):hover { background: #2563eb; }
  .primary.flash { background: #16a34a; }

  .secondary { background: #1e2d3d; color: #94a3b8; border: 1px solid #2d3748; }
  .secondary:not(:disabled):hover { background: #253447; }

  .note {
    font-size: 11px;
    color: #334155;
    line-height: 1.5;
  }
</style>
