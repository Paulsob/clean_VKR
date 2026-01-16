# src/scheduler.py
from src.database import DataLoader
from src.utils import calculate_duration_hours
from typing import List, Dict


class WorkforceAnalyzer:
    def __init__(self, db: DataLoader):
        self.db = db

    def generate_daily_roster(self, route_number: int, day_of_month: int, target_month: str):
        """
        Попытка расставить реальных людей на смены конкретного числа.
        """
        # 1. Находим расписание
        # (Упрощение: считаем, что день рабочий. Потом добавим логику выходного)
        schedule = next((s for s in self.db.schedules if s.route_number == route_number), None)
        if not schedule:
            return {"error": "Нет расписания"}

        # 2. Находим всех водителей, закрепленных за этим маршрутом
        assigned_drivers = [d for d in self.db.drivers if d.assigned_route_number == route_number]

        roster = []  # Сюда будем писать результат

        # 3. Пробегаем по трамваям
        for tram in schedule.trams:
            tram_result = {
                "tram_number": tram.number,
                "shift_1_driver": None,
                "shift_2_driver": None,
                "issues": []
            }

            # ПОИСК ВОДИТЕЛЯ НА 1 СМЕНУ
            if tram.shift_1:
                # Ищем того, кто:
                # а) Закреплен (уже отфильтровали)
                # б) В табеле на этот день стоит код работы (например "1" или "2" или "8")
                # в) Еще не назначен никуда сегодня (в этом цикле)

                candidate = self._find_driver(assigned_drivers, day_of_month, shift_type="morning")

                if candidate:
                    tram_result["shift_1_driver"] = str(candidate.id)
                    # Важно: помечаем водителя как занятого, чтобы не клонировать его
                    # (В реальности лучше использовать список занятых ID, но пока удалим из списка кандидатов)
                    assigned_drivers.remove(candidate)
                else:
                    tram_result["issues"].append("Не найден водитель на 1 смену!")

            # ПОИСК ВОДИТЕЛЯ НА 2 СМЕНУ
            if tram.shift_2:
                candidate = self._find_driver(assigned_drivers, day_of_month, shift_type="evening")

                if candidate:
                    tram_result["shift_2_driver"] = str(candidate.id)
                    assigned_drivers.remove(candidate)
                else:
                    tram_result["issues"].append("Не найден водитель на 2 смену!")

            roster.append(tram_result)

        return {
            "date": day_of_month,
            "route": route_number,
            "roster": roster,
            "drivers_leftover": [str(d.id) for d in assigned_drivers]  # Кто остался без работы
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