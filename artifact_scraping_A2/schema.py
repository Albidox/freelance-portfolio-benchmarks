"""Pydantic v2 schema for validated hockey team records."""
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, ValidationError


class TeamRecord(BaseModel):
    team_name: str = Field(..., min_length=1, description="Hockey team name")
    year: int = Field(..., ge=1900, le=2100, description="Season year")
    wins: int = Field(..., ge=0, description="Number of wins")
    losses: int = Field(..., ge=0, description="Number of losses")
    ot_losses: Optional[int] = Field(None, ge=0, description="Overtime losses (may be null)")
    win_pct: float = Field(..., ge=0.0, le=1.0, description="Win percentage 0.0-1.0")
    goals_for: int = Field(..., ge=0, description="Goals scored")
    goals_against: int = Field(..., ge=0, description="Goals conceded")
    goal_diff: int = Field(..., description="Goal differential (can be negative)")
    page_number: int = Field(..., ge=1, description="Source page number")

    @field_validator("win_pct", mode="before")
    @classmethod
    def parse_win_pct(cls, v: Any) -> float:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return 0.0
            return float(v)
        return float(v)

    @field_validator("ot_losses", mode="before")
    @classmethod
    def parse_ot_losses(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            return int(v)
        return int(v)


# Alias for compatibility across specifications
HockeyTeamRecord = TeamRecord
