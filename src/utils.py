# src/utils.py
from datetime import datetime, timedelta


def parse_time(time_str: str) -> datetime:
    """
    Превращает строку '04:43' в объект времени
    """
    return datetime.strptime(time_str, "%H:%M")


def calculate_duration_hours(start_str: str, end_str: str) -> float:
    """
    Считает длительность смены в часах.
    Учитывает переход через полночь (если начало в 23:00, а конец в 01:00).
    """
    start = parse_time(start_str)
    end = parse_time(end_str)

    if end < start:
        # Если время прибытия меньше времени отправления, значит смена перешла через полночь.
        # Добавляем 1 день к времени конца
        end += timedelta(days=1)

    duration = end - start
    # Возвращаем результат в часах
    return round(duration.total_seconds() / 3600, 2)
