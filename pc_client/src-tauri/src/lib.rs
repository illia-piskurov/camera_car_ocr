use std::sync::{Arc, Mutex};
use std::time::Duration;

use futures_util::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use simplelog::{CombinedLogger, Config, LevelFilter, WriteLogger};
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder,
};

fn init_logging() {
    let log_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("alpr_monitor.log")))
        .unwrap_or_else(|| std::path::PathBuf::from("alpr_monitor.log"));

    match std::fs::File::create(&log_path) {
        Ok(file) => {
            let _ = CombinedLogger::init(vec![WriteLogger::new(
                LevelFilter::Info,
                Config::default(),
                file,
            )]);
        }
        Err(e) => {
            // Can't write log file — at least print to stderr so terminal catches it
            eprintln!("Failed to create log file {log_path:?}: {e}");
        }
    }

    // Catch panics and write them to the log before dying
    std::panic::set_hook(Box::new(|info| {
        log::error!("PANIC: {info}");
        // Small sleep so the logger can flush
        std::thread::sleep(std::time::Duration::from_millis(200));
    }));
}

const DEFAULT_BACKEND_URL: &str = "http://localhost:8000";
const ALERT_LABEL: &str = "alert";
const SETTINGS_LABEL: &str = "settings";
const ALERT_W: f64 = 340.0;
const ALERT_H: f64 = 140.0;

// ── Types ─────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
struct RecognitionEvent {
    id: i64,
    occurred_at: String,
    plate: String,
    raw_plate: String,
    decision: String,
    reason_code: String,
    camera_id: Option<i64>,
    zone_id: Option<i64>,
    zone_name: Option<String>,
    ocr_confidence: f64,
    vote_confirmations: Option<i64>,
    vote_avg_confidence: Option<f64>,
    detection_confidence: f64,
    frame_id: String,
}

#[derive(Debug, Clone, Serialize)]
struct SseStatus {
    connected: bool,
    message: String,
}

struct AppState {
    backend_url: Arc<Mutex<String>>,
}

// ── Config file ────────────────────────────────────────────────────────────────

fn config_path(app: &AppHandle) -> std::path::PathBuf {
    app.path()
        .app_config_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."))
        .join("settings.json")
}

fn load_url(app: &AppHandle) -> String {
    let path = config_path(app);
    std::fs::read_to_string(&path)
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v.get("backend_url").and_then(|u| u.as_str()).map(String::from))
        .unwrap_or_else(|| DEFAULT_BACKEND_URL.to_string())
}

fn persist_url(app: &AppHandle, url: &str) {
    let path = config_path(app);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    let json = serde_json::json!({ "backend_url": url });
    std::fs::write(path, serde_json::to_string_pretty(&json).unwrap_or_default()).ok();
}

// ── Commands ───────────────────────────────────────────────────────────────────

#[tauri::command]
fn get_settings(state: tauri::State<AppState>) -> String {
    state.backend_url.lock().unwrap().clone()
}

#[tauri::command]
fn save_settings(url: String, state: tauri::State<AppState>, app: AppHandle) {
    *state.backend_url.lock().unwrap() = url.clone();
    persist_url(&app, &url);
}

// ── Window helpers ─────────────────────────────────────────────────────────────

fn ensure_alert_window(app: &AppHandle) -> tauri::WebviewWindow {
    if let Some(win) = app.get_webview_window(ALERT_LABEL) {
        return win;
    }

    log::info!("Creating alert window…");
    match WebviewWindowBuilder::new(app, ALERT_LABEL, WebviewUrl::App("/".into()))
        .title("ALPR Монітор")
        .inner_size(ALERT_W, ALERT_H)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .resizable(false)
        .visible(true)
        .transparent(true)
        .build()
    {
        Ok(win) => {
            log::info!("Alert window created OK");
            place_alert_window(&win);
            win
        }
        Err(e) => {
            log::error!("Failed to create alert window: {e}");
            panic!("Failed to create alert window: {e}");
        }
    }
}

fn place_alert_window(win: &tauri::WebviewWindow) {
    match win.primary_monitor() {
        Ok(Some(monitor)) => {
            let size = monitor.size();
            let scale = monitor.scale_factor();
            let screen_w = size.width as f64 / scale;
            let screen_h = size.height as f64 / scale;
            let x = screen_w - ALERT_W - 12.0;
            let y = screen_h - ALERT_H - 62.0;
            log::info!("Placing alert window at ({x}, {y}), screen {screen_w}x{screen_h} scale={scale}");
            win.set_position(tauri::LogicalPosition::new(x, y)).ok();
        }
        Ok(None) => log::warn!("primary_monitor() returned None — skipping placement"),
        Err(e) => log::warn!("primary_monitor() error: {e}"),
    }
}

fn open_settings_window(app: &AppHandle) {
    if let Some(win) = app.get_webview_window(SETTINGS_LABEL) {
        win.show().ok();
        win.set_focus().ok();
        return;
    }
    log::info!("Creating settings window…");
    match WebviewWindowBuilder::new(app, SETTINGS_LABEL, WebviewUrl::App("/settings".into()))
        .title("Налаштування — ALPR Монітор")
        .inner_size(440.0, 240.0)
        .resizable(false)
        .center()
        .build()
    {
        Ok(_) => log::info!("Settings window created OK"),
        Err(e) => log::error!("Failed to create settings window: {e}"),
    }
}

// ── SSE loop ───────────────────────────────────────────────────────────────────

fn parse_sse_block(block: &str) -> Option<RecognitionEvent> {
    block
        .lines()
        .find_map(|l| l.strip_prefix("data: "))
        .and_then(|data| serde_json::from_str(data.trim()).ok())
}

async fn fetch_start_id(client: &Client, base: &str) -> i64 {
    let url = format!("{}/api/events/latest-id", base);
    match client.get(&url).send().await {
        Ok(r) if r.status().is_success() => r
            .json::<serde_json::Value>().await
            .ok()
            .and_then(|v| v.get("id").and_then(|id| id.as_i64()))
            .unwrap_or(0),
        _ => 0,
    }
}

async fn sse_loop(app: AppHandle, backend_url: Arc<Mutex<String>>) {
    log::info!("SSE loop started");
    let client = Client::new();
    let mut last_id: i64 = 0;
    let mut last_base = String::new();

    loop {
        let base = backend_url.lock().unwrap().clone();

        // On first connect or URL change — skip all historical events
        if base != last_base {
            last_id = fetch_start_id(&client, &base).await;
            last_base = base.clone();
            log::info!("SSE starting from event id={last_id} (skipping history)");
        }

        let url = format!("{}/api/events/stream?after_id={}", base, last_id);
        log::info!("SSE connecting to {url}");

        app.emit("sse-status", SseStatus { connected: false, message: "Підключення…".into() }).ok();

        let response = match client.get(&url).send().await {
            Ok(r) if r.status().is_success() => r,
            Ok(r) => {
                log::warn!("SSE bad status: {}", r.status());
                app.emit("sse-status", SseStatus {
                    connected: false,
                    message: format!("HTTP {}", r.status()),
                }).ok();
                tokio::time::sleep(Duration::from_secs(5)).await;
                continue;
            }
            Err(e) => {
                log::warn!("SSE connect error: {e}");
                app.emit("sse-status", SseStatus {
                    connected: false,
                    message: "Помилка підключення".into(),
                }).ok();
                tokio::time::sleep(Duration::from_secs(5)).await;
                continue;
            }
        };

        log::info!("SSE connected, streaming…");
        app.emit("sse-status", SseStatus { connected: true, message: "Підключено".into() }).ok();

        let mut stream = response.bytes_stream();
        let mut buf = String::new();

        'read: loop {
            // 60s timeout between chunks — longer than our 15s keepalive
            match tokio::time::timeout(Duration::from_secs(60), stream.next()).await {
                Ok(Some(Ok(chunk))) => {
                    buf.push_str(&String::from_utf8_lossy(&chunk));

                    while let Some(pos) = buf.find("\n\n") {
                        let block = buf[..pos].to_string();
                        buf = buf[pos + 2..].to_string();

                        if block.trim_start().starts_with(':') {
                            continue; // SSE comment / keepalive
                        }

                        if let Some(event) = parse_sse_block(&block) {
                            last_id = event.id;
                            log::info!(
                                "Event #{} plate={} decision={} reason={}",
                                event.id, event.plate, event.decision, event.reason_code
                            );
                            if event.decision == "open" || event.decision == "deny" {
                                ensure_alert_window(&app);
                                app.emit("recognition-event", &event).ok();
                            }
                        }
                    }
                }
                Ok(Some(Err(e))) => {
                    log::warn!("SSE read error: {e}");
                    break 'read;
                }
                Ok(None) => break 'read,
                Err(_) => {
                    log::warn!("SSE keepalive timeout — reconnecting");
                    break 'read;
                }
            }
        }

        app.emit("sse-status", SseStatus { connected: false, message: "Перепідключення…".into() }).ok();
        tokio::time::sleep(Duration::from_secs(3)).await;
    }
}

// ── Entry point ────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    init_logging();
    log::info!("=== ALPR Монітор starting ===");

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(AppState {
            backend_url: Arc::new(Mutex::new(DEFAULT_BACKEND_URL.to_string())),
        })
        .invoke_handler(tauri::generate_handler![get_settings, save_settings])
        .setup(|app| {
            log::info!("setup() started");

            // Load persisted URL into shared state
            let saved = load_url(app.handle());
            log::info!("Loaded backend URL: {saved}");
            *app.state::<AppState>().backend_url.lock().unwrap() = saved;

            // Tray icon + menu
            log::info!("Building tray menu…");
            let item_settings =
                MenuItem::with_id(app, "settings", "Налаштування", true, None::<&str>)?;
            let sep = PredefinedMenuItem::separator(app)?;
            let item_quit = MenuItem::with_id(app, "quit", "Вийти", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&item_settings, &sep, &item_quit])?;

            TrayIconBuilder::new()
                .icon(app.default_window_icon().cloned().expect("no app icon configured"))
                .tooltip("ALPR Монітор")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "settings" => open_settings_window(app),
                    "quit" => std::process::exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|_tray, event| {
                    let _ = matches!(
                        event,
                        TrayIconEvent::Click {
                            button: MouseButton::Left,
                            button_state: MouseButtonState::Up,
                            ..
                        }
                    );
                })
                .build(app)?;

            log::info!("Tray icon built OK");

            // Pre-create hidden alert window
            log::info!("Pre-creating alert window…");
            ensure_alert_window(app.handle());

            // Start SSE background task
            log::info!("Spawning SSE task…");
            let app_handle = app.handle().clone();
            let url_arc = app.state::<AppState>().backend_url.clone();
            tauri::async_runtime::spawn(sse_loop(app_handle, url_arc));

            log::info!("setup() completed — app is running in tray");
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                match window.label() {
                    ALERT_LABEL => api.prevent_close(),
                    SETTINGS_LABEL => {
                        window.hide().ok();
                        api.prevent_close();
                    }
                    _ => {}
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app, event| match event {
            tauri::RunEvent::ExitRequested { api, .. } => {
                // Prevent Tauri from auto-exiting when all windows are hidden.
                // The process only ends via "Вийти" in the tray menu.
                log::info!("ExitRequested — preventing auto-exit (tray app)");
                api.prevent_exit();
            }
            tauri::RunEvent::Exit => {
                log::info!("App exiting normally");
            }
            _ => {}
        });
}
