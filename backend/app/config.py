from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    camera_snapshot_url: str = "http://192.168.30.206:86/ISAPI/Streaming/channels/502/picture"
    camera_username: str = ""
    camera_password: str = ""
    camera_auth_mode: str = "digest"
    poll_interval_sec: float = 0.4
    request_timeout_sec: float = 5.0
    request_retries: int = 2

    detector_model: str = "yolo-v9-t-384-license-plate-end2end"
    ocr_model: str = "global-plates-mobile-vit-v2-model"

    voting_window_sec: float = 1.5
    min_confirmations: int = 3
    min_avg_confidence: float = 0.80

    plate_cooldown_sec: float = 10.0
    global_cooldown_sec: float = 2.0
    dry_run_open: bool = True

    db_path: str = "data/app.db"
    onec_sync_interval_hours: float = 24.0
    onec_stub_file: str = "onec_whitelist_stub.txt"
    enable_fuzzy_match: bool = False

    preview_enabled: bool = True
    preview_write_interval_sec: float = 3.0
    preview_jpeg_quality: int = 85
    preview_image_path: str = "data/preview_latest.jpg"
    preview_meta_path: str = "data/preview_meta.json"

    recognition_snapshot_enabled: bool = True
    recognition_snapshot_dir: str = "data/recognized"
    recognition_snapshot_jpeg_quality: int = 90
    recognition_snapshot_max_files: int = 500
    detection_zones_max: int = 3

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            camera_snapshot_url=os.getenv("CAMERA_SNAPSHOT_URL", Settings.camera_snapshot_url),
            camera_username=os.getenv("CAMERA_USERNAME", Settings.camera_username),
            camera_password=os.getenv("CAMERA_PASSWORD", Settings.camera_password),
            camera_auth_mode=os.getenv("CAMERA_AUTH_MODE", Settings.camera_auth_mode),
            poll_interval_sec=float(os.getenv("POLL_INTERVAL_SEC", Settings.poll_interval_sec)),
            request_timeout_sec=float(os.getenv("REQUEST_TIMEOUT_SEC", Settings.request_timeout_sec)),
            request_retries=int(os.getenv("REQUEST_RETRIES", Settings.request_retries)),
            detector_model=os.getenv("DETECTOR_MODEL", Settings.detector_model),
            ocr_model=os.getenv("OCR_MODEL", Settings.ocr_model),
            voting_window_sec=float(os.getenv("VOTING_WINDOW_SEC", Settings.voting_window_sec)),
            min_confirmations=int(os.getenv("MIN_CONFIRMATIONS", Settings.min_confirmations)),
            min_avg_confidence=float(os.getenv("MIN_AVG_CONFIDENCE", Settings.min_avg_confidence)),
            plate_cooldown_sec=float(os.getenv("PLATE_COOLDOWN_SEC", Settings.plate_cooldown_sec)),
            global_cooldown_sec=float(os.getenv("GLOBAL_COOLDOWN_SEC", Settings.global_cooldown_sec)),
            dry_run_open=os.getenv("DRY_RUN_OPEN", "1") in {"1", "true", "True"},
            db_path=os.getenv("DB_PATH", Settings.db_path),
            onec_sync_interval_hours=float(
                os.getenv("ONEC_SYNC_INTERVAL_HOURS", Settings.onec_sync_interval_hours)
            ),
            onec_stub_file=os.getenv("ONEC_STUB_FILE", Settings.onec_stub_file),
            enable_fuzzy_match=os.getenv("ENABLE_FUZZY_MATCH", "0") in {"1", "true", "True"},
            preview_enabled=os.getenv("PREVIEW_ENABLED", "1") in {"1", "true", "True"},
            preview_write_interval_sec=float(
                os.getenv("PREVIEW_WRITE_INTERVAL_SEC", Settings.preview_write_interval_sec)
            ),
            preview_jpeg_quality=int(os.getenv("PREVIEW_JPEG_QUALITY", Settings.preview_jpeg_quality)),
            preview_image_path=os.getenv("PREVIEW_IMAGE_PATH", Settings.preview_image_path),
            preview_meta_path=os.getenv("PREVIEW_META_PATH", Settings.preview_meta_path),
            recognition_snapshot_enabled=os.getenv("RECOGNITION_SNAPSHOT_ENABLED", "1")
            in {"1", "true", "True"},
            recognition_snapshot_dir=os.getenv(
                "RECOGNITION_SNAPSHOT_DIR", Settings.recognition_snapshot_dir
            ),
            recognition_snapshot_jpeg_quality=int(
                os.getenv(
                    "RECOGNITION_SNAPSHOT_JPEG_QUALITY", Settings.recognition_snapshot_jpeg_quality
                )
            ),
            recognition_snapshot_max_files=int(
                os.getenv("RECOGNITION_SNAPSHOT_MAX_FILES", Settings.recognition_snapshot_max_files)
            ),
            detection_zones_max=int(os.getenv("DETECTION_ZONES_MAX", Settings.detection_zones_max)),
        )
