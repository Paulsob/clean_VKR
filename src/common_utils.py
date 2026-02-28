# src/common_utils.py
"""
Общие утилиты, используемые в разных частях проекта.
Устраняет дублирование кода.
"""
from typing import List, Tuple
from src.constants import get_month_number, MONTH_NAMES


def get_month_sequence(start_month_name: str, start_year: int, duration_months: int) -> List[Tuple[str, int]]:
    """
    Генерирует последовательность месяцев для симуляции.
    
    Args:
        start_month_name: Название начального месяца (например, "Январь")
        start_year: Начальный год
        duration_months: Количество месяцев
    
    Returns:
        Список кортежей (название_месяца, год)
    
    Example:
        >>> get_month_sequence("Декабрь", 2025, 3)
        [("Декабрь", 2025), ("Январь", 2026), ("Февраль", 2026)]
    """
    try:
        start_idx = get_month_number(start_month_name) - 1
    except ValueError:
        start_idx = 0
    
    sequence = []
    current_idx = start_idx
    current_year = start_year
    
    for _ in range(duration_months):
        month_name = MONTH_NAMES[current_idx]
        sequence.append((month_name, current_year))
        
        current_idx += 1
        if current_idx >= 12:
            current_idx = 0
            current_year += 1
    
    return sequence


def get_previous_month(month_name: str, year: int) -> Tuple[str, int]:
    """
    Возвращает предыдущий месяц.
    
    Args:
        month_name: Название текущего месяца
        year: Текущий год
    
    Returns:
        Кортеж (название_предыдущего_месяца, год)
    
    Example:
        >>> get_previous_month("Январь", 2026)
        ("Декабрь", 2025)
    """
    month_num = get_month_number(month_name)
    
    if month_num == 1:
        prev_month_num = 12
        prev_year = year - 1
    else:
        prev_month_num = month_num - 1
        prev_year = year
    
    prev_month_name = MONTH_NAMES[prev_month_num - 1]
    return prev_month_name, prev_year


def format_driver_id(raw_id: str) -> str:
    """
    Извлекает чистый ID водителя из строки с дополнительной информацией.
    
    Args:
        raw_id: Строка вида "101 (Вых!)" или просто "101"
    
    Returns:
        Чистый ID: "101"
    
    Example:
        >>> format_driver_id("101 (Вых!)")
        "101"
        >>> format_driver_id("42")
        "42"
    """
    return raw_id.split(" ")[0] if raw_id else ""


def safe_int_sort_key(value):
    """
    Безопасный ключ сортировки для значений, которые могут быть числами или строками.
    
    Args:
        value: Значение для сортировки
    
    Returns:
        Кортеж (приоритет, значение) для сортировки
    
    Example:
        >>> sorted(["10", "2", "abc"], key=safe_int_sort_key)
        ["2", "10", "abc"]
    """
    try:
        return (0, int(value))
    except (ValueError, TypeError):
        return (1, str(value))
