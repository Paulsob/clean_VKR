# src/scheduler_simple.py
"""
Упрощенный планировщик БЕЗ проверки отдыха.
Распределяет строго по табелю.
"""
from src.utils import get_day_type_by_date, get_weekday_name
from typing import List


class WorkforceAnalyzer:
    def __init__(self, db):
        self.db = db

    def generate_daily_roster(self, route_number: str, day_of_month: int,
                              target_month: str, target_year: int, **kwargs):

        current_day_type = get_day_type_by_date(day_of_month, target_month, year=target_year)
        current_day_name = get_weekday_name(day_of_month, target_month, year=target_year)

        # Находим расписание
        schedule = next((s for s in self.db.schedules if
                         str(s.route_number) == str(route_number) and
                         s.day_type.lower() == current_day_type), None)

        if not schedule:
            return {"error": f"Нет расписания ({current_day_type})"}

        # Списки водителей
        main_drivers = [d for d in self.db.drivers if
                        str(d.assigned_route_number) == str(route_number) and
                        d.month == target_month]

        reserve_drivers = [d for d in self.db.drivers if
                           str(d.assigned_route_number) == "ANY" and
                           d.month == target_month]

        roster = []

        for tram in schedule.trams:
            tram_result = {
                "tram_number": tram.number,
                "shift_1": {"driver": None},
                "shift_2": {"driver": None},
                "issues": []
            }

            # УТРЕННЯЯ СМЕНА
            if tram.shift_1:
                # Ищем водителя с табелем "1"
                driver = self._find_simple(main_drivers, day_of_month, "1")
                if not driver:
                    driver = self._find_simple(reserve_drivers, day_of_month, "1")

                if driver:
                    tram_result["shift_1"]["driver"] = str(driver.id)
                    # Убираем из доступных
                    if driver in main_drivers:
                        main_drivers.remove(driver)
                    else:
                        reserve_drivers.remove(driver)
                else:
                    tram_result["issues"].append("Нет водителя утро")

            # ВЕЧЕРНЯЯ СМЕНА
            if tram.shift_2:
                driver = self._find_simple(main_drivers, day_of_month, "2")
                if not driver:
                    driver = self._find_simple(reserve_drivers, day_of_month, "2")

                if driver:
                    tram_result["shift_2"]["driver"] = str(driver.id)
                    if driver in main_drivers:
                        main_drivers.remove(driver)
                    else:
                        reserve_drivers.remove(driver)
                else:
                    tram_result["issues"].append("Нет водителя вечер")

            roster.append(tram_result)

        return {
            "date": day_of_month,
            "day_type": current_day_type,
            "day_name": current_day_name,
            "route": route_number,
            "roster": roster
        }

    def _find_simple(self, drivers: List, day: int, shift: str):
        """Простой поиск по табелю"""
        for driver in drivers:
            if driver.get_status_for_day(day) == shift:
                return driver
        return None