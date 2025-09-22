"""SQLite repository for the local_league domain models."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterable, Iterator, List, Optional
import uuid

from .models import (
    EventDay,
    Match,
    MatchOutcome,
    Player,
    Season,
    SeasonMatrix,
    SeasonParticipant,
    SeasonStanding,
)


def _to_bool(value: int) -> bool:
    return bool(value)


def _iso_datetime(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat(timespec="seconds")


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _iso_date(value: date) -> str:
    return value.isoformat()


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _as_uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)


class LocalLeagueRepository:
    """Persistence layer backed by SQLite."""

    def __init__(self, path: str) -> None:
        self._path = path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        """Create tables if they do not already exist."""

        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS players (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS seasons (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    starts_on TEXT NOT NULL,
                    ends_on TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    description TEXT
                );

                CREATE TABLE IF NOT EXISTS season_participants (
                    season_id TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    seed INTEGER,
                    alias TEXT,
                    PRIMARY KEY (season_id, player_id),
                    FOREIGN KEY (season_id) REFERENCES seasons (id) ON DELETE CASCADE,
                    FOREIGN KEY (player_id) REFERENCES players (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    season_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    held_on TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (season_id) REFERENCES seasons (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS matches (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    player_one_id TEXT NOT NULL,
                    player_two_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    winner_id TEXT,
                    created_at TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                    FOREIGN KEY (player_one_id) REFERENCES players (id) ON DELETE CASCADE,
                    FOREIGN KEY (player_two_id) REFERENCES players (id) ON DELETE CASCADE,
                    FOREIGN KEY (winner_id) REFERENCES players (id)
                );
                """
            )

    # Player operations -------------------------------------------------
    def create_player(self, display_name: str, *, notes: Optional[str] = None) -> Player:
        player = Player(id=uuid.uuid4(), display_name=display_name, notes=notes)
        self.add_player(player)
        return player

    def add_player(self, player: Player) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO players (id, display_name, created_at, is_active, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(player.id),
                    player.display_name,
                    _iso_datetime(player.created_at),
                    int(player.is_active),
                    player.notes,
                ),
            )

    def list_players(self, *, active_only: bool = False) -> List[Player]:
        query = "SELECT * FROM players"
        params: tuple = ()
        if active_only:
            query += " WHERE is_active = 1"
            params = (1,)
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            Player(
                id=_as_uuid(row["id"]),
                display_name=row["display_name"],
                created_at=_parse_datetime(row["created_at"]),
                is_active=_to_bool(row["is_active"]),
                notes=row["notes"],
            )
            for row in rows
        ]

    def set_player_active(self, player_id: uuid.UUID, *, is_active: bool) -> None:
        with self._connection() as conn:
            conn.execute(
                "UPDATE players SET is_active = ? WHERE id = ?",
                (int(is_active), str(player_id)),
            )

    # Season operations -------------------------------------------------
    def add_season(self, season: Season) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO seasons (id, title, starts_on, ends_on, created_at, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(season.id),
                    season.title,
                    _iso_date(season.starts_on),
                    _iso_date(season.ends_on),
                    _iso_datetime(season.created_at),
                    season.description,
                ),
            )

    def list_seasons(self) -> List[Season]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM seasons ORDER BY starts_on").fetchall()
        return [
            Season(
                id=_as_uuid(row["id"]),
                title=row["title"],
                starts_on=_parse_date(row["starts_on"]),
                ends_on=_parse_date(row["ends_on"]),
                created_at=_parse_datetime(row["created_at"]),
                description=row["description"],
            )
            for row in rows
        ]

    def create_season(
        self,
        title: str,
        *,
        starts_on: date,
        ends_on: date,
        description: Optional[str] = None,
    ) -> Season:
        season = Season(
            id=uuid.uuid4(),
            title=title,
            starts_on=starts_on,
            ends_on=ends_on,
            description=description,
        )
        self.add_season(season)
        return season

    def add_season_participant(self, participant: SeasonParticipant) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO season_participants (season_id, player_id, seed, alias)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(participant.season_id),
                    str(participant.player_id),
                    participant.seed,
                    participant.alias,
                ),
            )

    def list_season_participants(self, season_id: uuid.UUID) -> List[SeasonParticipant]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM season_participants WHERE season_id = ? ORDER BY seed",
                (str(season_id),),
            ).fetchall()
        return [
            SeasonParticipant(
                season_id=_as_uuid(row["season_id"]),
                player_id=_as_uuid(row["player_id"]),
                seed=row["seed"],
                alias=row["alias"],
            )
            for row in rows
        ]

    def get_season(self, season_id: uuid.UUID) -> Optional[Season]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM seasons WHERE id = ?", (str(season_id),)).fetchone()
        if row is None:
            return None
        return Season(
            id=_as_uuid(row["id"]),
            title=row["title"],
            starts_on=_parse_date(row["starts_on"]),
            ends_on=_parse_date(row["ends_on"]),
            created_at=_parse_datetime(row["created_at"]),
            description=row["description"],
        )

    def update_season(self, season: Season) -> Optional[Season]:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                UPDATE seasons
                SET title = ?, starts_on = ?, ends_on = ?, description = ?
                WHERE id = ?
                """,
                (
                    season.title,
                    _iso_date(season.starts_on),
                    _iso_date(season.ends_on),
                    season.description,
                    str(season.id),
                ),
            )

        if cursor.rowcount == 0:
            return None
        return season

    def delete_season(self, season_id: uuid.UUID) -> bool:
        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM seasons WHERE id = ?", (str(season_id),))
        return cursor.rowcount > 0

    # Event operations --------------------------------------------------
    def add_event(self, event: EventDay) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO events (id, season_id, title, held_on, weight, created_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.id),
                    str(event.season_id),
                    event.title,
                    _iso_date(event.held_on),
                    event.weight,
                    _iso_datetime(event.created_at),
                    event.notes,
                ),
            )

    def create_event(
        self,
        season_id: uuid.UUID,
        title: str,
        *,
        held_on: date,
        weight: float = 1.0,
        notes: Optional[str] = None,
    ) -> EventDay:
        event = EventDay(
            id=uuid.uuid4(),
            season_id=season_id,
            title=title,
            held_on=held_on,
            weight=weight,
            notes=notes,
        )
        self.add_event(event)
        return event

    def list_events(self, season_id: uuid.UUID) -> List[EventDay]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE season_id = ? ORDER BY held_on",
                (str(season_id),),
            ).fetchall()
        return [
            EventDay(
                id=_as_uuid(row["id"]),
                season_id=_as_uuid(row["season_id"]),
                title=row["title"],
                held_on=_parse_date(row["held_on"]),
                weight=row["weight"],
                created_at=_parse_datetime(row["created_at"]),
                notes=row["notes"],
            )
            for row in rows
        ]

    # Match operations --------------------------------------------------
    def add_match(self, match: Match) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO matches (
                    id,
                    event_id,
                    player_one_id,
                    player_two_id,
                    outcome,
                    winner_id,
                    created_at,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(match.id),
                    str(match.event_id),
                    str(match.player_one_id),
                    str(match.player_two_id),
                    match.outcome.value,
                    str(match.winner_id) if match.winner_id else None,
                    _iso_datetime(match.created_at),
                    match.notes,
                ),
            )

    def create_match(
        self,
        event_id: uuid.UUID,
        *,
        player_one_id: uuid.UUID,
        player_two_id: uuid.UUID,
        outcome: MatchOutcome,
        winner_id: Optional[uuid.UUID],
        notes: Optional[str] = None,
    ) -> Match:
        match = Match(
            id=uuid.uuid4(),
            event_id=event_id,
            player_one_id=player_one_id,
            player_two_id=player_two_id,
            outcome=outcome,
            winner_id=winner_id,
            notes=notes,
        )
        self.add_match(match)
        return match

    def list_matches_for_events(self, event_ids: Iterable[uuid.UUID]) -> List[Match]:
        ids = [str(event_id) for event_id in event_ids]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        query = f"SELECT * FROM matches WHERE event_id IN ({placeholders})"
        with self._connection() as conn:
            rows = conn.execute(query, ids).fetchall()
        return [
            Match(
                id=_as_uuid(row["id"]),
                event_id=_as_uuid(row["event_id"]),
                player_one_id=_as_uuid(row["player_one_id"]),
                player_two_id=_as_uuid(row["player_two_id"]),
                outcome=MatchOutcome(row["outcome"]),
                winner_id=_as_uuid(row["winner_id"]) if row["winner_id"] else None,
                created_at=_parse_datetime(row["created_at"]),
                notes=row["notes"],
            )
            for row in rows
        ]

    # Reporting helpers -------------------------------------------------
    def compute_season_matrix(self, season_id: uuid.UUID) -> SeasonMatrix:
        season = self.get_season(season_id)
        if season is None:
            raise ValueError(f"Unknown season: {season_id}")

        participants = self.list_season_participants(season_id)
        player_ids = [participant.player_id for participant in participants]
        events = self.list_events(season_id)
        matches = self.list_matches_for_events(event.id for event in events)
        return SeasonMatrix.build(season_id, player_ids, events, matches)

    def compute_season_standings(self, season_id: uuid.UUID) -> List[SeasonStanding]:
        events = self.list_events(season_id)
        matches = self.list_matches_for_events(event.id for event in events)

        standings = {
            participant.player_id: SeasonStanding(season_id=season_id, player_id=participant.player_id)
            for participant in self.list_season_participants(season_id)
        }

        event_weights = {event.id: event.weight for event in events}
        for match in matches:
            weight = event_weights.get(match.event_id, 1.0)
            for player_id, standing in standings.items():
                if player_id in (match.player_one_id, match.player_two_id):
                    standing.record_match(match, weight)

        return list(standings.values())


__all__ = ["LocalLeagueRepository"]
