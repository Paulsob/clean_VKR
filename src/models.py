from pydantic import BaseModel, Field
from typing import List, Optional


class DayStatus(BaseModel):
    day: int
    value: str


class Driver(BaseModel):
    id: int = Field(alias="tab_number")  # В JSON: tab_number
    schedule_pattern: str = Field(alias="schedule")  # В JSON: schedule
    shift_preference: str = Field(alias="mode")  # В JSON: mode

    days_list: List[DayStatus] = Field(alias="days")

    assigned_route_number: Optional[int] = None

    def get_status_for_day(self, day_num: int) -> str:
        found = next((d for d in self.days_list if d.day == day_num), None)
        if found:
            return found.value
        return "Unknown"


class TimeWindow(BaseModel):
    start: str = Field(alias="отправление")
    end: str = Field(alias="прибытие")


class TramOutput(BaseModel):
    number: int = Field(alias="номер")
    shift_1: Optional[TimeWindow] = Field(default=None, alias="смена_1")
    shift_2: Optional[TimeWindow] = Field(default=None, alias="смена_2")


class RouteSchedule(BaseModel):
    route_number: int = Field(alias="маршрут")
    day_type: str = Field(alias="день")
    trams: List[TramOutput] = Field(alias="трамваи")


class Assignment(BaseModel):
    driver_id: int
    route_number: int
