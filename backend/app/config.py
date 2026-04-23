from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()

    if not key:
        return None

    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]

    return key, value


def _load_env_file_if_exists(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return

    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(line)
            if parsed is None:
                continue
            key, value = parsed
            os.environ.setdefault(key, value)
    except OSError:
        return


def _load_local_env_files() -> None:
    # Support local runs from backend/ while keeping repo-root .env as source of truth.
    current_file = Path(__file__).resolve()
    backend_dir = current_file.parents[1]
    repo_root = current_file.parents[2]

    _load_env_file_if_exists(backend_dir / ".env")
    _load_env_file_if_exists(repo_root / ".env")


@dataclass(frozen=True)
class Settings:
    camera_credentials_encryption_key: str = "camera-car-ocr-dev-key"
    poll_interval_sec: float = 0.4
    request_timeout_sec: float = 5.0
    request_retries: int = 2

    detector_model: str = "yolo-v9-t-384-license-plate-end2end"
    ocr_model: str = "global-plates-mobile-vit-v2-model"

    ocr_open_threshold: float = 0.92
    ocr_extend_threshold: float = 0.80
    two_shot_gap_ms: int = 200
    two_shot_max_pairs: int = 2

    dry_run_open: bool = True
    barrier_action_mode: str = "mock"
    barrier_ha_base_url: str = ""
    barrier_ha_token: str = ""
    zone1_barrier_open_entity_id: str = ""
    zone1_barrier_close_entity_id: str = ""
    zone1_barrier_close_delay_sec: float = 0.0
    zone2_barrier_open_entity_id: str = ""
    zone2_barrier_close_entity_id: str = ""
    zone2_barrier_close_delay_sec: float = 0.0
    barrier_request_timeout_sec: float = 3.0
    barrier_request_retries: int = 2
    barrier_verify_tls: bool = True
    barrier_close_delay_sec: float = 5.0

    db_path: str = "data/app.db"
    onec_sync_interval_hours: float = 24.0
    onec_provider_mode: str = "stub"
    onec_stub_file: str = "onec_whitelist_stub.txt"
    onec_http_url: str = ""
    onec_http_timeout_sec: float = 10.0
    onec_http_retries: int = 2
    onec_http_allow_empty_sync: bool = False
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
    detection_zones_max: int = 2

    motion_detection_enabled: bool = True
    motion_threshold_percent: float = 0.05
    motion_blur_kernel: int = 5

    def has_zone_barrier_entities(self, zone_id: int) -> bool:
        open_id, close_id = self.get_zone_barrier_entities(zone_id)
        return bool(open_id and close_id)

    def is_barrier_live_configured(self) -> bool:
        if not self.barrier_ha_base_url or not self.barrier_ha_token:
            return False
        return self.has_zone_barrier_entities(1) or self.has_zone_barrier_entities(2)

    def get_zone_barrier_entities(self, zone_id: int | None) -> tuple[str, str]:
        if zone_id == 1:
            return self.zone1_barrier_open_entity_id, self.zone1_barrier_close_entity_id
        if zone_id == 2:
            return self.zone2_barrier_open_entity_id, self.zone2_barrier_close_entity_id
        return "", ""

    def get_camera_credentials_encryption_key(self) -> str:
        return self.camera_credentials_encryption_key

    def _scoped_preview_path(self, base_path: str, camera_id: int | None) -> str:
        if camera_id is None:
            return base_path

        base = Path(base_path)
        suffix = base.suffix or ""
        return str(base.with_name(f"{base.stem}_camera_{camera_id}{suffix}"))

    def get_preview_image_path(self, camera_id: int | None = None) -> str:
        return self._scoped_preview_path(self.preview_image_path, camera_id)

    def get_preview_meta_path(self, camera_id: int | None = None) -> str:
        return self._scoped_preview_path(self.preview_meta_path, camera_id)

    def get_zone_close_delay_sec(self, zone_id: int | None) -> float:
        if zone_id == 1 and self.zone1_barrier_close_delay_sec > 0:
            return self.zone1_barrier_close_delay_sec
        if zone_id == 2 and self.zone2_barrier_close_delay_sec > 0:
            return self.zone2_barrier_close_delay_sec
        return self.barrier_close_delay_sec

    @staticmethod
    def from_env() -> "Settings":
        _load_local_env_files()
        return Settings(
            camera_credentials_encryption_key=os.getenv(
                "CAMERA_CREDENTIALS_ENCRYPTION_KEY", Settings.camera_credentials_encryption_key
            ),
            poll_interval_sec=float(os.getenv("POLL_INTERVAL_SEC", Settings.poll_interval_sec)),
            request_timeout_sec=float(os.getenv("REQUEST_TIMEOUT_SEC", Settings.request_timeout_sec)),
            request_retries=int(os.getenv("REQUEST_RETRIES", Settings.request_retries)),
            detector_model=os.getenv("DETECTOR_MODEL", Settings.detector_model),
            ocr_model=os.getenv("OCR_MODEL", Settings.ocr_model),
            ocr_open_threshold=float(
                os.getenv("OCR_OPEN_THRESHOLD", Settings.ocr_open_threshold)
            ),
            ocr_extend_threshold=float(
                os.getenv("OCR_EXTEND_THRESHOLD", Settings.ocr_extend_threshold)
            ),
            two_shot_gap_ms=int(os.getenv("TWO_SHOT_GAP_MS", Settings.two_shot_gap_ms)),
            two_shot_max_pairs=int(
                os.getenv("TWO_SHOT_MAX_PAIRS", Settings.two_shot_max_pairs)
            ),
            dry_run_open=os.getenv("DRY_RUN_OPEN", "1") in {"1", "true", "True"},
            barrier_action_mode=os.getenv("BARRIER_ACTION_MODE", Settings.barrier_action_mode),
            barrier_ha_base_url=os.getenv("BARRIER_HA_BASE_URL", Settings.barrier_ha_base_url),
            barrier_ha_token=os.getenv("BARRIER_HA_TOKEN", Settings.barrier_ha_token),
            zone1_barrier_open_entity_id=os.getenv(
                "ZONE1_BARRIER_OPEN_ENTITY_ID", Settings.zone1_barrier_open_entity_id
            ),
            zone1_barrier_close_entity_id=os.getenv(
                "ZONE1_BARRIER_CLOSE_ENTITY_ID", Settings.zone1_barrier_close_entity_id
            ),
            zone1_barrier_close_delay_sec=float(
                os.getenv("ZONE1_BARRIER_CLOSE_DELAY_SEC", Settings.zone1_barrier_close_delay_sec)
            ),
            zone2_barrier_open_entity_id=os.getenv(
                "ZONE2_BARRIER_OPEN_ENTITY_ID", Settings.zone2_barrier_open_entity_id
            ),
            zone2_barrier_close_entity_id=os.getenv(
                "ZONE2_BARRIER_CLOSE_ENTITY_ID", Settings.zone2_barrier_close_entity_id
            ),
            zone2_barrier_close_delay_sec=float(
                os.getenv("ZONE2_BARRIER_CLOSE_DELAY_SEC", Settings.zone2_barrier_close_delay_sec)
            ),
            barrier_request_timeout_sec=float(
                os.getenv("BARRIER_REQUEST_TIMEOUT_SEC", Settings.barrier_request_timeout_sec)
            ),
            barrier_request_retries=int(
                os.getenv("BARRIER_REQUEST_RETRIES", Settings.barrier_request_retries)
            ),
            barrier_verify_tls=os.getenv("BARRIER_VERIFY_TLS", "1") in {"1", "true", "True"},
            barrier_close_delay_sec=float(
                os.getenv("BARRIER_CLOSE_DELAY_SEC", Settings.barrier_close_delay_sec)
            ),
            db_path=os.getenv("DB_PATH", Settings.db_path),
            onec_sync_interval_hours=float(
                os.getenv("ONEC_SYNC_INTERVAL_HOURS", Settings.onec_sync_interval_hours)
            ),
            onec_provider_mode=os.getenv("ONEC_PROVIDER_MODE", Settings.onec_provider_mode),
            onec_stub_file=os.getenv("ONEC_STUB_FILE", Settings.onec_stub_file),
            onec_http_url=os.getenv("ONEC_HTTP_URL", Settings.onec_http_url),
            onec_http_timeout_sec=float(
                os.getenv("ONEC_HTTP_TIMEOUT_SEC", Settings.onec_http_timeout_sec)
            ),
            onec_http_retries=int(os.getenv("ONEC_HTTP_RETRIES", Settings.onec_http_retries)),
            onec_http_allow_empty_sync=os.getenv("ONEC_HTTP_ALLOW_EMPTY_SYNC", "0")
            in {"1", "true", "True"},
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
            motion_detection_enabled=os.getenv("MOTION_DETECTION_ENABLED", "1") in {"1", "true", "True"},
            motion_threshold_percent=float(
                os.getenv("MOTION_THRESHOLD_PERCENT", Settings.motion_threshold_percent)
            ),
            motion_blur_kernel=int(os.getenv("MOTION_BLUR_KERNEL", Settings.motion_blur_kernel)),
        )
