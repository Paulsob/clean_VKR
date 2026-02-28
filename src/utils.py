# src/utils.py
from datetime import datetime, timedelta
from src.constants import MONTH_MAP, WEEKDAY_NAMES, get_month_number

# Экспортируем для обратной совместимости
__all__ = ['get_month_number', 'get_day_type_by_date', 'get_weekday_name', 
           'parse_time', 'calculate_duration_hours']


def _get_date_obj(day: int, month_str: str, year: int):
    """Вспомогательная внутренняя функция создания даты"""
    month_num = MONTH_MAP.get(month_str)
    if not month_num:
        return None
    try:
        return datetime(year, month_num, day)
    except ValueError:
        return None


def get_day_type_by_date(day: int, month_str: str, year: int) -> str:
    """Определяет: рабочий или выходной"""
    date_obj = _get_date_obj(day, month_str, year)
    if not date_obj: return "рабочий"

    if date_obj.weekday() >= 5:
        return "выходной"
    else:
        return "рабочий"


def get_weekday_name(day: int, month_str: str, year: int) -> str:
    """Возвращает название дня: 'Понедельник', 'Вторник'..."""
    date_obj = _get_date_obj(day, month_str, year)
    if not date_obj: return "Неизвестно"

    return WEEKDAY_NAMES[date_obj.weekday()]


def parse_time(time_str: str) -> datetime:
    return datetime.strptime(time_str, "%H:%M")


def calculate_duration_hours(start_str: str, end_str: str) -> float:
    start = parse_time(start_str)
    end = parse_time(end_str)
    if end < start:
        end += timedelta(days=1)
    duration = end - start
    return round(duration.total_seconds() / 3600, 2)

