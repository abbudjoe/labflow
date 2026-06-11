"""96-well coordinate parsing and ordering."""

from __future__ import annotations

import re
from functools import total_ordering
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WELL_RE = re.compile(r"^([A-Ha-h])([1-9]|1[0-2])$")
ROW_ORDER = tuple("ABCDEFGH")


@total_ordering
class WellCoordinate(BaseModel):
    """A validated 96-well coordinate such as A1 or H12."""

    model_config = ConfigDict(frozen=True)

    row: str = Field(min_length=1, max_length=1)
    column: int = Field(ge=1, le=12)

    @model_validator(mode="before")
    @classmethod
    def parse_input(cls, data: Any) -> Any:
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            match = WELL_RE.match(data.strip())
            if not match:
                msg = f"Invalid 96-well coordinate: {data!r}"
                raise ValueError(msg)
            row, column = match.groups()
            return {"row": row.upper(), "column": int(column)}
        return data

    @field_validator("row")
    @classmethod
    def validate_row(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in ROW_ORDER:
            msg = f"Well row must be A-H, got {value!r}"
            raise ValueError(msg)
        return normalized

    @property
    def row_index(self) -> int:
        return ROW_ORDER.index(self.row)

    @property
    def sort_key(self) -> tuple[int, int]:
        return (self.row_index, self.column)

    def __str__(self) -> str:
        return f"{self.row}{self.column}"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, WellCoordinate):
            return NotImplemented
        return self.sort_key < other.sort_key

    def __hash__(self) -> int:
        return hash((self.row, self.column))


def parse_well(value: str | WellCoordinate) -> WellCoordinate:
    return WellCoordinate.model_validate(value)


def default_standard_wells() -> list[WellCoordinate]:
    return [parse_well(f"{row}1") for row in ROW_ORDER]


def all_plate_wells() -> list[WellCoordinate]:
    return [parse_well(f"{row}{column}") for row in ROW_ORDER for column in range(1, 13)]
