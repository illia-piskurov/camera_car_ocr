from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, create_engine, event, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .security import decrypt_text, encrypt_text


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_or_now(value: datetime | None) -> datetime:
    normalized = _as_utc(value)
    return normalized if normalized is not None else utc_now()


class WhitelistPlate(Base):
    __tablename__ = "whitelist_plates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plate: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    fuzzy_plate: Mapped[str] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(50), default="stub")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SyncState(Base):
    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_full_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CameraGroup(Base):
    __tablename__ = "camera_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    cross_suppress_sec: Mapped[int] = mapped_column(Integer, default=120)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    snapshot_url: Mapped[str] = mapped_column(String(512))
    username_encrypted: Mapped[str] = mapped_column(String(1024), default="")
    password_encrypted: Mapped[str] = mapped_column(String(1024), default="")
    auth_mode: Mapped[str] = mapped_column(String(32), default="digest")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("camera_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DetectionZone(Base):
    __tablename__ = "detection_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    ha_open_entity_id: Mapped[str] = mapped_column(String(128), default="")
    ha_close_entity_id: Mapped[str] = mapped_column(String(128), default="")
    x_min: Mapped[float] = mapped_column(Float)
    y_min: Mapped[float] = mapped_column(Float)
    x_max: Mapped[float] = mapped_column(Float)
    y_max: Mapped[float] = mapped_column(Float)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    cross_camera_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cross_zone_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("detection_zones.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RecognitionEvent(Base):
    __tablename__ = "recognition_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    frame_id: Mapped[str] = mapped_column(String(64), index=True)
    raw_plate: Mapped[str] = mapped_column(String(32))
    plate: Mapped[str] = mapped_column(String(32), index=True)
    fuzzy_plate: Mapped[str] = mapped_column(String(32), index=True)
    detection_confidence: Mapped[float] = mapped_column(Float)
    ocr_confidence: Mapped[float] = mapped_column(Float)
    vote_confirmations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vote_avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    zone_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    zone_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    reason_code: Mapped[str] = mapped_column(String(64))


class Database:
    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            future=True,
            connect_args={"timeout": 15},
        )
        self._configure_sqlite_pragmas()
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)

    def _configure_sqlite_pragmas(self) -> None:
        @event.listens_for(self.engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=15000;")
            cursor.close()

    def init(self) -> None:
        Base.metadata.create_all(self.engine)
        self._migrate()

    def _migrate(self) -> None:
        with self.engine.connect() as conn:
            cam_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(cameras)"))}
            if "group_id" not in cam_cols:
                conn.execute(text("ALTER TABLE cameras ADD COLUMN group_id INTEGER REFERENCES camera_groups(id) ON DELETE SET NULL"))
                conn.commit()

            zone_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(detection_zones)"))}
            if "cross_camera_enabled" not in zone_cols:
                conn.execute(text("ALTER TABLE detection_zones ADD COLUMN cross_camera_enabled INTEGER NOT NULL DEFAULT 1"))
                conn.commit()
            if "cross_zone_id" not in zone_cols:
                conn.execute(text("ALTER TABLE detection_zones ADD COLUMN cross_zone_id INTEGER REFERENCES detection_zones(id) ON DELETE SET NULL"))
                conn.commit()

    def _camera_row(self, row: Camera) -> dict[str, object]:
        return {
            "id": row.id,
            "name": row.name,
            "snapshot_url": row.snapshot_url,
            "auth_mode": row.auth_mode,
            "is_active": bool(row.is_active),
            "sort_order": int(row.sort_order),
            "group_id": row.group_id,
            "created_at": _utc_or_now(row.created_at).isoformat(),
            "updated_at": _utc_or_now(row.updated_at).isoformat(),
            "has_credentials": bool(row.username_encrypted or row.password_encrypted),
        }

    def _group_row(self, row: CameraGroup) -> dict[str, object]:
        return {
            "id": row.id,
            "name": row.name,
            "cross_suppress_sec": int(row.cross_suppress_sec),
            "created_at": _utc_or_now(row.created_at).isoformat(),
            "updated_at": _utc_or_now(row.updated_at).isoformat(),
        }

    def list_cameras(self, is_active: bool | None = None) -> list[dict[str, object]]:
        with self.SessionLocal() as session:
            query = select(Camera).order_by(Camera.sort_order.asc(), Camera.id.asc())
            if is_active is not None:
                query = query.where(Camera.is_active == is_active)
            rows = session.execute(query).scalars().all()
            return [self._camera_row(row) for row in rows]

    def get_camera(self, camera_id: int) -> dict[str, object] | None:
        with self.SessionLocal() as session:
            row = session.get(Camera, camera_id)
            return self._camera_row(row) if row is not None else None

    # ------------------------------------------------------------------ groups

    def list_camera_groups(self) -> list[dict[str, object]]:
        with self.SessionLocal() as session:
            rows = session.execute(select(CameraGroup).order_by(CameraGroup.name.asc())).scalars().all()
            return [self._group_row(r) for r in rows]

    def get_camera_group(self, group_id: int) -> dict[str, object] | None:
        with self.SessionLocal() as session:
            row = session.get(CameraGroup, group_id)
            return self._group_row(row) if row is not None else None

    def create_camera_group(self, *, name: str, cross_suppress_sec: int = 120) -> dict[str, object]:
        with self.SessionLocal() as session:
            row = CameraGroup(name=name.strip(), cross_suppress_sec=cross_suppress_sec, created_at=utc_now(), updated_at=utc_now())
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._group_row(row)

    def update_camera_group(
        self,
        group_id: int,
        *,
        name: str | None = None,
        cross_suppress_sec: int | None = None,
    ) -> dict[str, object] | None:
        with self.SessionLocal() as session:
            row = session.get(CameraGroup, group_id)
            if row is None:
                return None
            if name is not None and name.strip():
                row.name = name.strip()
            if cross_suppress_sec is not None:
                row.cross_suppress_sec = max(0, cross_suppress_sec)
            row.updated_at = utc_now()
            session.commit()
            session.refresh(row)
            return self._group_row(row)

    def delete_camera_group(self, group_id: int) -> bool:
        with self.SessionLocal() as session:
            row = session.get(CameraGroup, group_id)
            if row is None:
                return False
            session.execute(
                text("UPDATE cameras SET group_id = NULL WHERE group_id = :gid"),
                {"gid": group_id},
            )
            session.delete(row)
            session.commit()
            return True

    # ----------------------------------------------------------------- cameras

    def create_camera(
        self,
        *,
        name: str,
        snapshot_url: str,
        username: str,
        password: str,
        auth_mode: str,
        encryption_key: str,
        is_active: bool = True,
        sort_order: int | None = None,
        group_id: int | None = None,
    ) -> dict[str, object]:
        with self.SessionLocal() as session:
            if sort_order is None:
                max_sort = session.scalar(select(func.max(Camera.sort_order)))
                sort_order = int(max_sort or 0) + 1

            camera = Camera(
                name=name,
                snapshot_url=snapshot_url,
                username_encrypted=encrypt_text(username, encryption_key),
                password_encrypted=encrypt_text(password, encryption_key),
                auth_mode=auth_mode or "digest",
                is_active=is_active,
                sort_order=sort_order,
                group_id=group_id,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(camera)
            session.commit()
            session.refresh(camera)
            return self._camera_row(camera)

    def update_camera(
        self,
        camera_id: int,
        *,
        name: str | None = None,
        snapshot_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        auth_mode: str | None = None,
        encryption_key: str,
        is_active: bool | None = None,
        sort_order: int | None = None,
        group_id: int | None | type[...] = ...,
    ) -> dict[str, object] | None:
        with self.SessionLocal() as session:
            row = session.get(Camera, camera_id)
            if row is None:
                return None

            if name is not None and name.strip():
                row.name = name.strip()
            if snapshot_url is not None and snapshot_url.strip():
                row.snapshot_url = snapshot_url.strip()
            if username is not None and username.strip():
                row.username_encrypted = encrypt_text(username, encryption_key)
            if password is not None and password.strip():
                row.password_encrypted = encrypt_text(password, encryption_key)
            if auth_mode is not None and auth_mode.strip():
                row.auth_mode = auth_mode.strip()
            if is_active is not None:
                row.is_active = is_active
            if sort_order is not None:
                row.sort_order = sort_order
            if group_id is not ...:
                row.group_id = group_id

            row.updated_at = utc_now()
            session.commit()
            session.refresh(row)
            return self._camera_row(row)

    def delete_camera(self, camera_id: int) -> bool:
        with self.SessionLocal() as session:
            row = session.get(Camera, camera_id)
            if row is None:
                return False

            session.query(DetectionZone).filter(DetectionZone.camera_id == camera_id).delete(synchronize_session=False)
            session.query(RecognitionEvent).filter(RecognitionEvent.camera_id == camera_id).delete(synchronize_session=False)
            session.delete(row)
            session.commit()
            return True

    def get_camera_credentials(self, camera_id: int, encryption_key: str) -> tuple[str, str, str] | None:
        with self.SessionLocal() as session:
            row = session.get(Camera, camera_id)
            if row is None:
                return None
            return (
                decrypt_text(row.username_encrypted or "", encryption_key),
                decrypt_text(row.password_encrypted or "", encryption_key),
                row.auth_mode,
            )

    def get_group_peer_zones(self, camera_id: int) -> list[dict[str, object]]:
        """Return zones from all peer cameras in the same group, with camera name attached."""
        with self.SessionLocal() as session:
            cam = session.get(Camera, camera_id)
            if cam is None or cam.group_id is None:
                return []
            peer_cam_rows = session.execute(
                select(Camera)
                .where(Camera.group_id == cam.group_id)
                .where(Camera.id != camera_id)
                .order_by(Camera.sort_order.asc(), Camera.id.asc())
            ).scalars().all()
            result = []
            for peer in peer_cam_rows:
                zones = session.execute(
                    select(DetectionZone)
                    .where(DetectionZone.camera_id == peer.id)
                    .order_by(DetectionZone.sort_order.asc(), DetectionZone.id.asc())
                ).scalars().all()
                for z in zones:
                    result.append({
                        "id": z.id,
                        "camera_id": peer.id,
                        "camera_name": peer.name,
                        "name": z.name,
                    })
            return result

    def is_cross_camera_suppressed(self, plate: str, camera_id: int, zone_id: int | None = None, max_distance: int = 0) -> bool:
        """Return True if a peer zone (or any peer camera in the group) recently opened for this plate.

        If zone_id is given and the zone has cross_camera_enabled=False → not suppressed.
        If zone_id is given and cross_zone_id is set → check only that specific zone.
        Otherwise → check all peer cameras in the group (group-level fallback).
        """
        with self.SessionLocal() as session:
            cam = session.get(Camera, camera_id)
            if cam is None or cam.group_id is None:
                return False

            group = session.get(CameraGroup, cam.group_id)
            if group is None or group.cross_suppress_sec <= 0:
                return False

            cutoff = utc_now() - timedelta(seconds=group.cross_suppress_sec)

            # Zone-level config
            target_zone_ids: list[int] | None = None
            if zone_id is not None:
                zone_row = session.get(DetectionZone, zone_id)
                if zone_row is not None:
                    if not zone_row.cross_camera_enabled:
                        return False
                    if zone_row.cross_zone_id is not None:
                        cross_zone = session.get(DetectionZone, zone_row.cross_zone_id)
                        if cross_zone is None:
                            return False
                        target_zone_ids = [zone_row.cross_zone_id]

            if target_zone_ids is None:
                # Group-level: all peer cameras
                peer_cameras = session.execute(
                    select(Camera.id)
                    .where(Camera.group_id == cam.group_id)
                    .where(Camera.id != camera_id)
                ).scalars().all()
                if not peer_cameras:
                    return False
                stmt = (
                    select(RecognitionEvent.plate)
                    .where(RecognitionEvent.decision == "open")
                    .where(RecognitionEvent.camera_id.in_(peer_cameras))
                    .where(RecognitionEvent.occurred_at >= cutoff)
                )
            else:
                stmt = (
                    select(RecognitionEvent.plate)
                    .where(RecognitionEvent.decision == "open")
                    .where(RecognitionEvent.zone_id.in_(target_zone_ids))
                    .where(RecognitionEvent.occurred_at >= cutoff)
                )

            peer_plates = session.execute(stmt).scalars().all()

            if not peer_plates:
                return False

            if max_distance <= 0:
                return plate in peer_plates

            from .fuzzy_edit import levenshtein_bounded
            return any(levenshtein_bounded(plate, p, max_distance) <= max_distance for p in peer_plates)

    def ping(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def upsert_whitelist(self, normalized_plates: list[tuple[str, str]], source: str = "stub") -> int:
        with self.SessionLocal() as session:
            existing = {
                row.plate: row
                for row in session.execute(select(WhitelistPlate)).scalars().all()
            }

            incoming = {plate for plate, _ in normalized_plates}
            for plate, fuzzy in normalized_plates:
                item = existing.get(plate)
                if item is None:
                    session.add(
                        WhitelistPlate(
                            plate=plate,
                            fuzzy_plate=fuzzy,
                            is_active=True,
                            source=source,
                            updated_at=utc_now(),
                        )
                    )
                else:
                    item.fuzzy_plate = fuzzy
                    item.is_active = True
                    item.source = source
                    item.updated_at = utc_now()

            for plate, item in existing.items():
                if plate not in incoming:
                    item.is_active = False
                    item.updated_at = utc_now()

            session.commit()
        return len(normalized_plates)

    def get_active_plates(self) -> list[str]:
        """Return all active normalized plate strings for in-memory fuzzy matching."""
        with self.SessionLocal() as session:
            rows = session.execute(
                select(WhitelistPlate.plate).where(WhitelistPlate.is_active.is_(True))
            ).scalars().all()
            return list(rows)

    def is_whitelisted(self, plate: str, fuzzy_plate: str, enable_fuzzy_match: bool) -> bool:
        with self.SessionLocal() as session:
            strict_match = session.scalar(
                select(WhitelistPlate)
                .where(WhitelistPlate.plate == plate)
                .where(WhitelistPlate.is_active.is_(True))
            )
            if strict_match is not None:
                return True

            if not enable_fuzzy_match:
                return False

            fuzzy_match = session.scalar(
                select(WhitelistPlate)
                .where(WhitelistPlate.fuzzy_plate == fuzzy_plate)
                .where(WhitelistPlate.is_active.is_(True))
            )
            return fuzzy_match is not None

    def record_event(
        self,
        *,
        occurred_at: datetime,
        frame_id: str,
        raw_plate: str,
        plate: str,
        fuzzy_plate: str,
        detection_confidence: float,
        ocr_confidence: float,
        decision: str,
        reason_code: str,
        vote_confirmations: int | None = None,
        vote_avg_confidence: float | None = None,
        zone_id: int | None = None,
        zone_name: str | None = None,
        camera_id: int | None = None,
    ) -> None:
        with self.SessionLocal() as session:
            session.add(
                RecognitionEvent(
                    camera_id=camera_id,
                    occurred_at=occurred_at,
                    frame_id=frame_id,
                    raw_plate=raw_plate,
                    plate=plate,
                    fuzzy_plate=fuzzy_plate,
                    detection_confidence=detection_confidence,
                    ocr_confidence=ocr_confidence,
                    vote_confirmations=vote_confirmations,
                    vote_avg_confidence=vote_avg_confidence,
                    zone_id=zone_id,
                    zone_name=zone_name,
                    decision=decision,
                    reason_code=reason_code,
                )
            )
            session.commit()

    def replace_zones(
        self,
        zones: list[dict[str, object]],
        max_zones: int = 2,
        camera_id: int | None = None,
    ) -> list[dict[str, object]]:
        limited = zones[: max(0, max_zones)]
        with self.SessionLocal() as session:
            stmt = session.query(DetectionZone)
            if camera_id is None:
                stmt = stmt.filter(DetectionZone.camera_id.is_(None))
            else:
                stmt = stmt.filter(DetectionZone.camera_id == camera_id)
            stmt.delete(synchronize_session=False)

            for index, zone in enumerate(limited):
                raw_cross_zone_id = zone.get("cross_zone_id")
                session.add(
                    DetectionZone(
                        camera_id=camera_id,
                        name=str(zone.get("name") or f"Zone {index + 1}"),
                        ha_open_entity_id=str(zone.get("ha_open_entity_id") or zone.get("open_entity_id") or ""),
                        ha_close_entity_id=str(zone.get("ha_close_entity_id") or zone.get("close_entity_id") or ""),
                        x_min=float(zone.get("x_min", 0.0)),
                        y_min=float(zone.get("y_min", 0.0)),
                        x_max=float(zone.get("x_max", 1.0)),
                        y_max=float(zone.get("y_max", 1.0)),
                        is_enabled=bool(zone.get("is_enabled", True)),
                        sort_order=int(zone.get("sort_order", index)),
                        cross_camera_enabled=bool(zone.get("cross_camera_enabled", True)),
                        cross_zone_id=int(raw_cross_zone_id) if raw_cross_zone_id is not None else None,
                        updated_at=utc_now(),
                    )
                )

            session.commit()

        return self.get_zones(include_disabled=True, camera_id=camera_id)

    def get_zones(self, include_disabled: bool = False, camera_id: int | None = None) -> list[dict[str, object]]:
        with self.SessionLocal() as session:
            stmt = select(DetectionZone).order_by(DetectionZone.sort_order.asc(), DetectionZone.id.asc())
            if camera_id is not None:
                stmt = stmt.where(DetectionZone.camera_id == camera_id)
            else:
                stmt = stmt.where(DetectionZone.camera_id.is_(None))
            if not include_disabled:
                stmt = stmt.where(DetectionZone.is_enabled.is_(True))

            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": row.id,
                    "camera_id": row.camera_id,
                    "name": row.name,
                    "ha_open_entity_id": row.ha_open_entity_id,
                    "ha_close_entity_id": row.ha_close_entity_id,
                    "x_min": float(row.x_min),
                    "y_min": float(row.y_min),
                    "x_max": float(row.x_max),
                    "y_max": float(row.y_max),
                    "is_enabled": bool(row.is_enabled),
                    "sort_order": int(row.sort_order),
                    "cross_camera_enabled": bool(row.cross_camera_enabled),
                    "cross_zone_id": row.cross_zone_id,
                }
                for row in rows
            ]

    def set_last_sync_now(self) -> None:
        with self.SessionLocal() as session:
            state = session.get(SyncState, 1)
            if state is None:
                state = SyncState(id=1, last_full_sync_at=utc_now())
                session.add(state)
            else:
                state.last_full_sync_at = utc_now()
            session.commit()

    def is_sync_due(self, every_hours: float) -> bool:
        with self.SessionLocal() as session:
            state = session.get(SyncState, 1)
            if state is None or state.last_full_sync_at is None:
                return True
            last_sync = _as_utc(state.last_full_sync_at)
            if last_sync is None:
                return True
            return utc_now() - last_sync >= timedelta(hours=every_hours)

    def get_last_sync_at(self) -> datetime | None:
        with self.SessionLocal() as session:
            state = session.get(SyncState, 1)
            if state is None:
                return None
            return _as_utc(state.last_full_sync_at)

    def get_whitelist_counts(self) -> dict[str, int]:
        with self.SessionLocal() as session:
            active = session.scalar(
                select(func.count(WhitelistPlate.id)).where(WhitelistPlate.is_active.is_(True))
            )
            inactive = session.scalar(
                select(func.count(WhitelistPlate.id)).where(WhitelistPlate.is_active.is_(False))
            )
            return {
                "active": int(active or 0),
                "inactive": int(inactive or 0),
            }

    def get_decision_counts_since(self, since: datetime, camera_id: int | None = None) -> dict[str, int]:
        threshold = _utc_or_now(since)
        with self.SessionLocal() as session:
            stmt = select(RecognitionEvent.decision, func.count(RecognitionEvent.id)).where(
                RecognitionEvent.occurred_at >= threshold
            )
            if camera_id is not None:
                stmt = stmt.where(RecognitionEvent.camera_id == camera_id)
            rows = session.execute(stmt.group_by(RecognitionEvent.decision)).all()

            counts = {"open": 0, "deny": 0, "observed": 0}
            for decision, value in rows:
                key = str(decision)
                counts[key] = int(value)
            return counts

    def get_recent_events(self, limit: int = 25, camera_id: int | None = None) -> list[dict[str, object]]:
        with self.SessionLocal() as session:
            stmt = select(RecognitionEvent).order_by(RecognitionEvent.occurred_at.desc())
            if camera_id is not None:
                stmt = stmt.where(RecognitionEvent.camera_id == camera_id)
            rows = session.execute(stmt.limit(limit)).scalars()

            result: list[dict[str, object]] = []
            for row in rows:
                occurred_at = _utc_or_now(row.occurred_at)
                result.append(
                    {
                        "id": row.id,
                        "occurred_at": occurred_at.isoformat(),
                        "frame_id": row.frame_id,
                        "raw_plate": row.raw_plate,
                        "plate": row.plate,
                        "decision": row.decision,
                        "reason_code": row.reason_code,
                        "detection_confidence": row.detection_confidence,
                        "ocr_confidence": row.ocr_confidence,
                        "vote_confirmations": row.vote_confirmations,
                        "vote_avg_confidence": row.vote_avg_confidence,
                        "zone_id": row.zone_id,
                        "zone_name": row.zone_name,
                        "camera_id": row.camera_id,
                    }
                )
            return result

    def get_event_frame_id(self, event_id: int) -> str | None:
        with self.SessionLocal() as session:
            row = session.get(RecognitionEvent, event_id)
            if row is None:
                return None
            return row.frame_id
