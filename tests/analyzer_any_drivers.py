import unittest
from datetime import datetime, date, timedelta
from typing import List, Any
import sys
from unittest.mock import MagicMock


# --- MOCKS ---

class MockDriver:
    def __init__(self, id, assigned_route_number, month, status_map):
        self.id = id
        self.assigned_route_number = assigned_route_number
        self.month = month
        self.status_map = status_map

    def get_status_for_day(self, day):
        return self.status_map.get(day, "В")


class MockShift:
    def __init__(self, start, end):
        self.start = start
        self.end = end


class MockTram:
    def __init__(self, number, s1_start, s1_end, s2_start=None, s2_end=None):
        self.number = number
        self.shift_1 = MockShift(s1_start, s1_end) if s1_start else None
        self.shift_2 = MockShift(s2_start, s2_end) if s2_start else None


class MockSchedule:
    def __init__(self, route_number, day_type, trams):
        self.route_number = route_number
        self.day_type = day_type
        self.trams = trams


class MockDB:
    def __init__(self):
        self.drivers = []
        self.schedules = []
        self.absences = []


# --- Имитация функции (ПРОСТАЯ ВЕРСИЯ) ---
def mock_get_day_type(day, month, year):
    # 9 Января 2026 - Пятница (рабочий)
    # 10 Января 2026 - Суббота (выходной)
    dt = date(year, 1, day)
    if dt.weekday() >= 5: return "выходной"
    return "рабочий"


# --- ИМПОРТ ВАШЕГО КЛАССА ---
# Укажите здесь правильный путь к WorkforceAnalyzer
# Например: from src.modules.simulation_core import WorkforceAnalyzer
from src.core.scheduler import WorkforceAnalyzer

# Подменяем функцию внутри модуля (грязный хак для теста, если utils импортируется внутри)
# Но лучше передать функцию или использовать patch.
# Для простоты, в коде WorkforceAnalyzer, который вы прислали, импорт такой:
# from src.utils import get_day_type_by_date
# Мы должны запатчить его в том модуле, где лежит WorkforceAnalyzer
from unittest.mock import patch


class TestReserveDistribution(unittest.TestCase):

    def setUp(self):
        self.db = MockDB()

        # Расписание "рабочий" для 10-го маршрута
        trams = [
            MockTram("101", "08:00", "16:00", "16:00", "23:59"),  # 2 смены
            MockTram("102", "09:00", "17:00")  # 1 смена
        ]
        self.db.schedules.append(MockSchedule("10", "рабочий", trams))

        # Расписание "рабочий" для 20-го маршрута (для теста конфликтов)
        self.db.schedules.append(MockSchedule("20", "рабочий", [
            MockTram("201", "08:00", "16:00")
        ]))

        # Дата теста: 9 января (Пятница - рабочий)
        self.test_day = 9
        self.test_year = 2026

    @patch('src.simulation.workforce_analyzer.get_day_type_by_date', side_effect=mock_get_day_type)
    def test_single_shift_per_day_same_route(self, mock_utils):
        """Проверка: Резервный водитель не берет 2 смены на одном маршруте в один день"""
        analyzer = WorkforceAnalyzer(self.db)

        # Водитель 7 (ANY) хочет работать ("1") 9-го числа
        res_driver = MockDriver(7, "ANY", "Январь", {9: "1"})
        self.db.drivers = [res_driver]

        result = analyzer.generate_daily_roster("10", self.test_day, "Январь", self.test_year, mode="strict")

        if "error" in result:
            self.fail(f"Ошибка генерации: {result['error']}")

        roster = result['roster']

        # Считаем назначения водителя 7
        count_7 = 0
        for tram in roster:
            if tram.get('shift_1') and tram['shift_1']['driver'] == '7': count_7 += 1
            if tram.get('shift_2') and tram['shift_2']['driver'] == '7': count_7 += 1

        print(f"\nТест 1: Водитель 7 назначен {count_7} раз(а)")
        self.assertEqual(count_7, 1)

    @patch('src.simulation.workforce_analyzer.get_day_type_by_date', side_effect=mock_get_day_type)
    def test_rest_regime_between_days(self, mock_utils):
        """Проверка: Соблюдение отдыха (вчера работал до поздна)"""
        analyzer = WorkforceAnalyzer(self.db)

        # Вчера (8-го) закончил в 23:59. Сегодня (9-го) смена в 08:00. Разрыв 8ч < 12ч.
        analyzer.history = {
            "7": {
                'end_dt': datetime(2026, 1, 8, 23, 59),
                'duration': 8.0
            }
        }

        res_driver = MockDriver(7, "ANY", "Январь", {9: "1"})
        self.db.drivers = [res_driver]

        result = analyzer.generate_daily_roster("10", self.test_day, "Январь", self.test_year, mode="strict")

        if "error" in result: self.fail(result['error'])

        # Трамвай 101, Смена 1 (08:00)
        tram101 = next(t for t in result['roster'] if t['tram_number'] == "101")
        assigned = tram101['shift_1']

        print(f"\nТест 2 (Отдых): {assigned}")
        self.assertIsNone(assigned, "Должно быть пусто из-за недоотдыха")

    @patch('src.simulation.workforce_analyzer.get_day_type_by_date', side_effect=mock_get_day_type)
    def test_cross_route_conflict(self, mock_utils):
        """Проверка: Конфликт между маршрутами"""
        analyzer = WorkforceAnalyzer(self.db)

        res_driver = MockDriver(7, "ANY", "Январь", {9: "1"})
        self.db.drivers = [res_driver]

        # 1. Маршрут 10
        analyzer.generate_daily_roster("10", self.test_day, "Январь", self.test_year, mode="strict")

        self.assertIn("7", analyzer.history, "Водитель должен быть в истории после 1-го маршрута")

        # 2. Маршрут 20 (то же время)
        result_20 = analyzer.generate_daily_roster("20", self.test_day, "Январь", self.test_year, mode="strict")

        tram201 = result_20['roster'][0]
        assigned = tram201.get('shift_1')

        print(f"\nТест 3 (Конфликт): Назначение на М20 -> {assigned}")
        self.assertIsNone(assigned, "Водитель не должен работать на 2 маршрутах")


if __name__ == '__main__':
    unittest.main()