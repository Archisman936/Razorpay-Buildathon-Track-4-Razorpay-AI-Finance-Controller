from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database: dict
    models: dict


class ErrorResponse(BaseModel):
    detail: str
