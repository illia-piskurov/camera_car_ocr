from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, create_engine, event, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


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


class RecognitionEvent(Base):
    __tablename__ = "recognition_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    frame_id: Mapped[str] = mapped_column(String(64), index=True)
    raw_plate: Mapped[str] = mapped_column(String(32))
    plate: Mapped[str] = mapped_column(String(32), index=True)
    fuzzy_plate: Mapped[str] = mapped_column(String(32), index=True)
    detection_confidence: Mapped[float] = mapped_column(Float)
    ocr_confidence: Mapped[float] = mapped_column(Float)
    vote_confirmations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vote_avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    ) -> None:
        with self.SessionLocal() as session:
            session.add(
                RecognitionEvent(
                    occurred_at=occurred_at,
                    frame_id=frame_id,
                    raw_plate=raw_plate,
                    plate=plate,
                    fuzzy_plate=fuzzy_plate,
                    detection_confidence=detection_confidence,
                    ocr_confidence=ocr_confidence,
                    vote_confirmations=vote_confirmations,
                    vote_avg_confidence=vote_avg_confidence,
                    decision=decision,
                    reason_code=reason_code,
                )
            )
            session.commit()

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

    def get_decision_counts_since(self, since: datetime) -> dict[str, int]:
        threshold = _utc_or_now(since)
        with self.SessionLocal() as session:
            rows = session.execute(
                select(RecognitionEvent.decision, func.count(RecognitionEvent.id))
                .where(RecognitionEvent.occurred_at >= threshold)
                .group_by(RecognitionEvent.decision)
            ).all()

            counts = {"open": 0, "deny": 0, "observed": 0}
            for decision, value in rows:
                key = str(decision)
                counts[key] = int(value)
            return counts

    def get_recent_events(self, limit: int = 25) -> list[dict[str, object]]:
        with self.SessionLocal() as session:
            rows = session.execute(
                select(RecognitionEvent)
                .order_by(RecognitionEvent.occurred_at.desc())
                .limit(limit)
            ).scalars()

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
                    }
                )
            return result

    def get_event_frame_id(self, event_id: int) -> str | None:
        with self.SessionLocal() as session:
            row = session.get(RecognitionEvent, event_id)
            if row is None:
                return None
            return row.frame_id
