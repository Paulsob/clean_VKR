from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SimulationMode(str, Enum):
    REAL = "real"
    STRICT = "strict"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SimulationRequest(BaseModel):
    month: str
    year: int
    routes: Optional[List[str]] = None
    mode: SimulationMode = SimulationMode.REAL


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: Optional[str] = None
    progress: Optional[float] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None


class SystemStatus(BaseModel):
    status: str
    current_month: str
    current_year: int
    process_all_routes: bool
    database_status: str
    drivers_count: int
    routes_count: int


class DriverInfo(BaseModel):
    id: int
    assigned_route_number: Optional[str] = None
    schedule_pattern: str
    month: Optional[str] = None
    shift_preference: str

    @classmethod
    def from_driver(cls, driver):
        return cls(
            id=driver.id,
            assigned_route_number=driver.assigned_route_number,
            schedule_pattern=driver.schedule_pattern,
            month=driver.month,
            shift_preference=driver.shift_preference
        )


class DriverInfo(BaseModel):
    id: int
    assigned_route_number: Optional[str] = None
    schedule_pattern: str
    month: Optional[str] = None
    shift_preference: str

    @classmethod
    def from_driver(cls, driver):
        """Конвертер из внутренней модели Driver в модель API DriverInfo"""
        return cls(
            id=driver.id,
            assigned_route_number=driver.assigned_route_number,
            schedule_pattern=driver.schedule_pattern,
            month=driver.month,
            shift_preference=driver.shift_preference
        )


class DriversResponse(BaseModel):
    drivers: List[DriverInfo]
    total: int
