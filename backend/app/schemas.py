"""The only operations a cloud model is allowed to request."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Filter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1, max_length=250)
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "is_null", "not_null"]
    value: Any = None

    @field_validator("value")
    @classmethod
    def scalar_or_list(cls, value: Any) -> Any:
        def scalar(v: Any) -> bool:
            return v is None or isinstance(v, (str, int, float, bool))
        if isinstance(value, list):
            if len(value) > 200 or not all(scalar(item) for item in value):
                raise ValueError("Filter lists must contain at most 200 scalar values.")
        elif not scalar(value):
            raise ValueError("A filter value must be a scalar or a list of scalars.")
        if len(str(value)) > 10000:
            raise ValueError("Filter value is too long.")
        return value


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["select", "sum", "count", "average", "min", "max", "group", "missing", "duplicates", "percentage", "percentage_change", "compare"]
    column: str | None = Field(default=None, max_length=250)
    group_by: str | None = Field(default=None, max_length=250)
    aggregate: Literal["sum", "count", "average", "min", "max"] = "sum"
    filters: list[Filter] = Field(default_factory=list, max_length=20)
    comparison_filters: list[Filter] = Field(default_factory=list, max_length=20)
    sort_by: str | None = Field(default=None, max_length=250)
    descending: bool = False
    limit: int = Field(default=20, ge=1, le=200)
    date_group: Literal["day", "month", "year"] | None = None
    clarification: str | None = Field(default=None, max_length=1000)
    interpretation: str = Field(default="", max_length=2000)
