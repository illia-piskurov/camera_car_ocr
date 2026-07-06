"""Fetches and caches the latest security-client (pc_client) Windows build from GitHub Actions.

The security PC has no internet access, so the guard app installer can't be pulled directly
from GitHub. Instead the backend (which does have internet) downloads the latest successful
build artifact once, caches the installer on disk, and re-serves it to admins over the LAN.
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import Settings

LOG = logging.getLogger(__name__)

_METADATA_FILENAME = "metadata.json"
_API_BASE = "https://api.github.com"


class PcClientReleaseError(Exception):
    """Raised when the latest release can't be resolved or downloaded from GitHub."""


@dataclass
class ReleaseInfo:
    artifact_id: int
    run_id: int
    branch: str
    created_at: str
    size_bytes: int


def _headers(cfg: Settings) -> dict[str, str]:
    if not cfg.pc_client_github_token:
        raise PcClientReleaseError("PC_CLIENT_GITHUB_TOKEN is not configured")
    return {
        "Authorization": f"Bearer {cfg.pc_client_github_token}",
        "Accept": "application/vnd.github+json",
    }


def fetch_latest_release_info(cfg: Settings) -> ReleaseInfo:
    """Look up the newest non-expired artifact for the client app, without downloading it."""
    url = f"{_API_BASE}/repos/{cfg.pc_client_github_repo}/actions/artifacts"
    try:
        response = httpx.get(url, headers=_headers(cfg), params={"per_page": 30}, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise PcClientReleaseError(f"Failed to reach GitHub: {exc}") from exc

    artifacts = response.json().get("artifacts", [])
    for artifact in artifacts:
        if artifact.get("name") != cfg.pc_client_artifact_name:
            continue
        if artifact.get("expired"):
            continue
        run = artifact.get("workflow_run") or {}
        return ReleaseInfo(
            artifact_id=artifact["id"],
            run_id=run.get("id", 0),
            branch=run.get("head_branch", ""),
            created_at=artifact["created_at"],
            size_bytes=artifact["size_in_bytes"],
        )

    raise PcClientReleaseError(f"No non-expired '{cfg.pc_client_artifact_name}' artifact found")


def _cache_dir(cfg: Settings) -> Path:
    path = Path(cfg.pc_client_release_cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_cached_metadata(cfg: Settings) -> dict | None:
    meta_path = _cache_dir(cfg) / _METADATA_FILENAME
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def get_cached_installer_path(cfg: Settings) -> tuple[Path, dict] | None:
    """Return the cached installer path + metadata, if a cached build exists on disk."""
    meta = _read_cached_metadata(cfg)
    if meta is None:
        return None
    installer_path = _cache_dir(cfg) / meta["filename"]
    if not installer_path.exists():
        return None
    return installer_path, meta


def _extract_installer(zip_bytes: bytes, dest_dir: Path) -> Path:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = archive.namelist()
        exe_name = next((n for n in names if n.lower().endswith(".exe")), None)
        chosen = exe_name or next((n for n in names if n.lower().endswith(".msi")), None)
        if chosen is None:
            raise PcClientReleaseError("Artifact zip contains no .exe or .msi installer")

        dest_path = dest_dir / Path(chosen).name
        with archive.open(chosen) as src, open(dest_path, "wb") as dst:
            dst.write(src.read())
        return dest_path


def ensure_cached_installer(cfg: Settings) -> tuple[Path, dict]:
    """Ensure the latest build is downloaded and cached locally, then return its path.

    Skips re-downloading if the cached build already matches the latest artifact id.
    """
    latest = fetch_latest_release_info(cfg)
    cached = _read_cached_metadata(cfg)
    dest_dir = _cache_dir(cfg)

    if cached and cached.get("artifact_id") == latest.artifact_id:
        installer_path = dest_dir / cached["filename"]
        if installer_path.exists():
            return installer_path, cached

    LOG.info("Downloading pc_client artifact id=%s run_id=%s", latest.artifact_id, latest.run_id)
    download_url = f"{_API_BASE}/repos/{cfg.pc_client_github_repo}/actions/artifacts/{latest.artifact_id}/zip"
    try:
        response = httpx.get(download_url, headers=_headers(cfg), timeout=60.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise PcClientReleaseError(f"Failed to download artifact from GitHub: {exc}") from exc

    installer_path = _extract_installer(response.content, dest_dir)

    metadata = {
        "artifact_id": latest.artifact_id,
        "run_id": latest.run_id,
        "branch": latest.branch,
        "created_at": latest.created_at,
        "size_bytes": latest.size_bytes,
        "filename": installer_path.name,
    }
    (dest_dir / _METADATA_FILENAME).write_text(json.dumps(metadata), encoding="utf-8")
    return installer_path, metadata
