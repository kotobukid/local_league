"""FastAPI application exposing CRUD endpoints for seasons."""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import List, Optional
import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .models import Season
from .repository import LocalLeagueRepository


DATABASE_PATH = os.getenv("LOCAL_LEAGUE_DB_PATH", "local_league.db")

app = FastAPI(title="Local League API")

_repository = LocalLeagueRepository(DATABASE_PATH)


@app.on_event("startup")
def _initialize_schema() -> None:
    _repository.initialize_schema()


def get_repository() -> LocalLeagueRepository:
    """Provide the repository instance for FastAPI dependencies."""

    return _repository


class SeasonBase(BaseModel):
    title: str = Field(..., min_length=1)
    starts_on: date
    ends_on: date
    description: Optional[str] = None


class SeasonCreate(SeasonBase):
    pass


class SeasonUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    description: Optional[str] = None


class SeasonResponse(BaseModel):
    id: uuid.UUID
    title: str
    starts_on: date
    ends_on: date
    created_at: datetime
    description: Optional[str]


def _season_to_response(season: Season) -> SeasonResponse:
    return SeasonResponse(
        id=season.id,
        title=season.title,
        starts_on=season.starts_on,
        ends_on=season.ends_on,
        created_at=season.created_at,
        description=season.description,
    )


def _validate_date_range(starts_on: date, ends_on: date) -> None:
    if ends_on < starts_on:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ends_on must be on or after starts_on",
        )


@app.get("/seasons", response_model=List[SeasonResponse])
def list_seasons(
    repository: LocalLeagueRepository = Depends(get_repository),
) -> List[SeasonResponse]:
    seasons = repository.list_seasons()
    return [_season_to_response(season) for season in seasons]


@app.post("/seasons", response_model=SeasonResponse, status_code=status.HTTP_201_CREATED)
def create_season(
    payload: SeasonCreate,
    repository: LocalLeagueRepository = Depends(get_repository),
) -> SeasonResponse:
    _validate_date_range(payload.starts_on, payload.ends_on)
    season = repository.create_season(
        title=payload.title,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        description=payload.description,
    )
    return _season_to_response(season)


@app.get("/seasons/{season_id}", response_model=SeasonResponse)
def get_season(
    season_id: uuid.UUID,
    repository: LocalLeagueRepository = Depends(get_repository),
) -> SeasonResponse:
    season = repository.get_season(season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return _season_to_response(season)


@app.put("/seasons/{season_id}", response_model=SeasonResponse)
def update_season(
    season_id: uuid.UUID,
    payload: SeasonUpdate,
    repository: LocalLeagueRepository = Depends(get_repository),
) -> SeasonResponse:
    existing = repository.get_season(season_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")

    updated = Season(
        id=existing.id,
        title=payload.title if payload.title is not None else existing.title,
        starts_on=payload.starts_on if payload.starts_on is not None else existing.starts_on,
        ends_on=payload.ends_on if payload.ends_on is not None else existing.ends_on,
        created_at=existing.created_at,
        description=payload.description if payload.description is not None else existing.description,
    )

    _validate_date_range(updated.starts_on, updated.ends_on)

    saved = repository.update_season(updated)
    if saved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return _season_to_response(saved)


@app.delete("/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_season(
    season_id: uuid.UUID,
    repository: LocalLeagueRepository = Depends(get_repository),
) -> None:
    deleted = repository.delete_season(season_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")

