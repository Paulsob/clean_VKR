from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Union


# --- Вспомогательная модель для одного дня. Используется внутри Driver для хранения табеля ---
class DayStatus(BaseModel):
    day: int
    value: str


# --- Основная модель водителя ---
class Driver(BaseModel):
    id: int = Field(alias="tab_number")
    schedule_pattern: str = Field(alias="schedule")
    shift_preference: str = Field(alias="mode")
    days_list: List[DayStatus] = Field(alias="days")
    assigned_route_number: Optional[str] = None
    month: Optional[str] = None

    def get_status_for_day(self, day_num: int) -> str:
        found = next((d for d in self.days_list if d.day == day_num), None)
        if found:
            return found.value
        return "Unknown"


# --- Модели маршрута ---
class TimeWindow(BaseModel):
    start: str = Field(alias="отправление")
    end: str = Field(alias="прибытие")


class TramOutput(BaseModel):
    # Разрешаем (Union) и строку, и число на входе
    number: Union[str, int] = Field(alias="номер")
    shift_1: Optional[TimeWindow] = Field(default=None, alias="смена_1")
    shift_2: Optional[TimeWindow] = Field(default=None, alias="смена_2")

    # ВАЛИДАТОР: Превращает int в str автоматически
    @field_validator('number')
    @classmethod
    def force_string(cls, v):
        return str(v)


class RouteSchedule(BaseModel):
    # Разрешаем и строку, и число
    route_number: Union[str, int] = Field(alias="маршрут")
    day_type: str = Field(alias="день")
    trams: List[TramOutput] = Field(alias="трамваи")

    # ВАЛИДАТОР: Превращает int в str автоматически
    @field_validator('route_number')
    @classmethod
    def force_string(cls, v):
        return str(v)


# --- Модель закрепления ---
class Assignment(BaseModel):
    driver_id: int
    route_number: Union[str, int]  # И тут разрешаем число

    # ВАЛИДАТОР: Превращает int в str автоматически
    @field_validator('route_number')
    @classmethod
    def force_string(cls, v):
        return str(v)


class Absence(BaseModel):
    driver_id: str
    type: str  # 'sick' | 'vacation'
    start_date: str = Field(alias="from")
    end_date: str = Field(alias="to")
    comment: Optional[str] = ""

    # Можно добавить метод, который проверяет дату
    def is_active(self, check_date):
        # Превращаем строки в date
        d_from = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        d_to = datetime.strptime(self.end_date, "%Y-%m-%d").date()
        return d_from <= check_date <= d_to
