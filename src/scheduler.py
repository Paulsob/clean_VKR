# src/scheduler.py
from src.database import DataLoader
from src.utils import get_day_type_by_date, get_weekday_name
from typing import List


class WorkforceAnalyzer:
    def __init__(self, db: DataLoader):
        self.db = db

    def generate_daily_roster(self, route_number: str, day_of_month: int, target_month: str, target_year: int):

        # ... (Код определения даты и поиска расписания - без изменений) ...
        # (Просто скопируй начало из старого файла)
        current_day_type = get_day_type_by_date(day_of_month, target_month, year=target_year)
        current_day_name = get_weekday_name(day_of_month, target_month, year=target_year)

        schedule = next((s for s in self.db.schedules if
                         str(s.route_number) == str(route_number) and s.day_type.lower() == current_day_type), None)
        if not schedule: return {"error": f"Нет расписания ({current_day_type})"}


        # Список 1: "СВОИ" (Штатные)
        main_drivers = [
            d for d in self.db.drivers
            if str(d.assigned_route_number) == str(route_number) and d.month == target_month
        ]

        # Список 2: "РЕЗЕРВ" (ANY)
        reserve_drivers = [
            d for d in self.db.drivers
            if str(d.assigned_route_number) == "ANY" and d.month == target_month
        ]

        print(f"👥 Водителей: Штатных {len(main_drivers)} | Резерв {len(reserve_drivers)}")

        roster = []

        for tram in schedule.trams:
            tram_result = {
                "tram_number": tram.number,
                "shift_1_driver": None,
                "shift_2_driver": None,
                "issues": []
            }


            # 1 СМЕНА
            if tram.shift_1:
                # Попытка 1: Ищем среди СВОИХ
                cand = self._find_driver(main_drivers, day_of_month, "morning")
                if cand:
                    tram_result["shift_1_driver"] = str(cand.id)
                    main_drivers.remove(cand)  # Убираем из списка доступных
                else:
                    # Попытка 2: Ищем в РЕЗЕРВЕ
                    cand = self._find_driver(reserve_drivers, day_of_month, "morning")
                    if cand:
                        tram_result["shift_1_driver"] = f"{cand.id} (БЕЗ МАРШРУТА)"
                        reserve_drivers.remove(cand)
                    else:
                        tram_result["issues"].append("Нет водителя (утро)")

            # 2 СМЕНА (Аналогично)
            if tram.shift_2:
                # Попытка 1: СВОИ
                cand = self._find_driver(main_drivers, day_of_month, "evening")
                if cand:
                    tram_result["shift_2_driver"] = str(cand.id)
                    main_drivers.remove(cand)
                else:
                    # Попытка 2: РЕЗЕРВ
                    cand = self._find_driver(reserve_drivers, day_of_month, "evening")
                    if cand:
                        tram_result["shift_2_driver"] = f"{cand.id} (БЕЗ МАРШРУТА)"
                        reserve_drivers.remove(cand)
                    else:
                        tram_result["issues"].append("Нет водителя (вечер)")

            roster.append(tram_result)

        return {
            "date": day_of_month,
            "day_type": current_day_type,
            "day_name": current_day_name,
            "route": route_number,
            "roster": roster,
            "drivers_leftover": [str(d.id) for d in main_drivers]
        }


    def _find_driver(self, drivers: List, day: int, shift_type: str):
        """
        Ищет водителя СТРОГО по коду в табеле на этот день.
        Никакой самодеятельности.
        """
        for driver in drivers:
            status = driver.get_status_for_day(day)  # Тут будет "1", "2", "В" или "Б"

            # --- ИЩЕМ НА УТРО ---
            if shift_type == "morning":
                # Берем только тех, у кого в табеле стоит "1"
                if status == "1":
                    return driver

            # --- ИЩЕМ НА ВЕЧЕР ---
            elif shift_type == "evening":
                # Берем только тех, у кого в табеле стоит "2"
                if status == "2":
                    return driver

            # Любой другой статус ("В", "Б", "О", или не та смена) -> Игнорируем

        return None