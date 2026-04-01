from pydantic import BaseModel, Field
from datetime import datetime


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class CreateRunRequest(BaseModel):
    id: str | None = None
    name: str | None = None
    config: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class DefineMetricRequest(BaseModel):
    key: str
    type: str = "scalar"
    direction: str = "neutral"
    description: str = ""
    aggregation: str = "last"


class MetricPointIn(BaseModel):
    key: str
    step: int
    value: float
    timestamp: str | None = None


class LogEntryIn(BaseModel):
    step: int | None = None
    level: str = "info"
    content: str
    timestamp: str | None = None


class UpdateRunRequest(BaseModel):
    status: str
