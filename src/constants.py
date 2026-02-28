# src/constants.py
"""
Константы и базовые утилиты без внешних зависимостей.
Этот модуль не должен импортировать ничего из src.* (кроме стандартной библиотеки).
"""

# Карты для перевода месяцев
MONTH_MAP = {
    "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6,
    "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12
}

MONTH_NAMES = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

WEEKDAY_NAMES = [
    "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"
]


def get_month_number(month_name: str) -> int:
    """
    Преобразует название месяца в номер (1-12).
    
    Args:
        month_name: Название месяца на русском (например, "Январь")
    
    Returns:
        Номер месяца (1-12)
    
    Raises:
        ValueError: Если месяц не найден
    """
    if month_name in MONTH_MAP:
        return MONTH_MAP[month_name]
    else:
        raise ValueError(f"Unknown month: {month_name}")


def get_month_name(month_number: int) -> str:
    """
    Преобразует номер месяца в название.
    
    Args:
        month_number: Номер месяца (1-12)
    
    Returns:
        Название месяца на русском
    
    Raises:
        ValueError: Если номер месяца некорректен
    """
    if 1 <= month_number <= 12:
        return MONTH_NAMES[month_number - 1]
    else:
        raise ValueError(f"Invalid month number: {month_number}. Must be 1-12.")
