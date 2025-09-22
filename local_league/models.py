"""Domain models for the local_league project.

These dataclasses capture the domain described in README.md. They are designed
for persistence in a SQLite database, but they remain storage-agnostic so they
can be serialized to JSON or YAML when needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
import uuid
from typing import Dict, Iterable, List, Optional


class MatchOutcome(Enum):
    """Supported outcomes for a head-to-head match."""

    PLAYER_ONE_WIN = "player_one_win"
    PLAYER_TWO_WIN = "player_two_win"
    DRAW = "draw"


@dataclass(frozen=True)
class Player:
    """Represents a participant that can join multiple seasons."""

    id: uuid.UUID
    display_name: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    notes: Optional[str] = None


@dataclass(frozen=True)
class SeasonParticipant:
    """Association between a season and a player."""

    season_id: uuid.UUID
    player_id: uuid.UUID
    seed: Optional[int] = None
    alias: Optional[str] = None


@dataclass(frozen=True)
class Season:
    """A month-long aggregation of events."""

    id: uuid.UUID
    title: str
    starts_on: date
    ends_on: date
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: Optional[str] = None


@dataclass(frozen=True)
class EventDay:
    """Represents the day-long tournament previously called a "フェス"."""

    id: uuid.UUID
    season_id: uuid.UUID
    title: str
    held_on: date
    weight: float = 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    notes: Optional[str] = None


@dataclass(frozen=True)
class Match:
    """A single head-to-head match record between two players."""

    id: uuid.UUID
    event_id: uuid.UUID
    player_one_id: uuid.UUID
    player_two_id: uuid.UUID
    outcome: MatchOutcome
    winner_id: Optional[uuid.UUID]
    created_at: datetime = field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

    def points_for_player(self, player_id: uuid.UUID, weight: float = 1.0) -> float:
        """Return the weighted points awarded to ``player_id``."""

        if self.outcome is MatchOutcome.DRAW:
            return 0.5 * weight
        if self.winner_id is None:
            return 0.0
        return weight if self.winner_id == player_id else 0.0

    def opponent_of(self, player_id: uuid.UUID) -> Optional[uuid.UUID]:
        """Return the opponent's player ID for ``player_id``."""

        if player_id == self.player_one_id:
            return self.player_two_id
        if player_id == self.player_two_id:
            return self.player_one_id
        return None


@dataclass
class SeasonStanding:
    """Aggregate statistics for a player within a season."""

    season_id: uuid.UUID
    player_id: uuid.UUID
    wins: int = 0
    losses: int = 0
    draws: int = 0
    weighted_points: float = 0.0

    def record_match(self, match: Match, event_weight: float) -> None:
        """Update standing based on the provided match."""

        if match.outcome is MatchOutcome.DRAW:
            self.draws += 1
            self.weighted_points += event_weight * 0.5
            return

        if match.winner_id == self.player_id:
            self.wins += 1
            self.weighted_points += event_weight
        elif match.winner_id is not None:
            self.losses += 1


@dataclass
class SeasonMatrix:
    """Matrix representation used by the WebUI."""

    season_id: uuid.UUID
    player_order: List[uuid.UUID]
    rows: Dict[uuid.UUID, Dict[uuid.UUID, float]] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        season_id: uuid.UUID,
        player_ids: Iterable[uuid.UUID],
        events: Iterable[EventDay],
        matches: Iterable[Match],
    ) -> "SeasonMatrix":
        """Construct a matrix of weighted points per head-to-head matchup."""

        player_order = list(player_ids)
        rows: Dict[uuid.UUID, Dict[uuid.UUID, float]] = {
            player_id: {opponent_id: 0.0 for opponent_id in player_order}
            for player_id in player_order
        }

        event_weights: Dict[uuid.UUID, float] = {event.id: event.weight for event in events}

        for match in matches:
            weight = event_weights.get(match.event_id, 1.0)
            if match.outcome is MatchOutcome.DRAW:
                rows[match.player_one_id][match.player_two_id] += weight * 0.5
                rows[match.player_two_id][match.player_one_id] += weight * 0.5
                continue

            if match.winner_id == match.player_one_id:
                rows[match.player_one_id][match.player_two_id] += weight
            elif match.winner_id == match.player_two_id:
                rows[match.player_two_id][match.player_one_id] += weight

        return cls(season_id=season_id, player_order=player_order, rows=rows)


__all__ = [
    "EventDay",
    "Match",
    "MatchOutcome",
    "Player",
    "Season",
    "SeasonMatrix",
    "SeasonParticipant",
    "SeasonStanding",
]
