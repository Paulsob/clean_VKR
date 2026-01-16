import json
import os
from typing import List
from src.models import Driver, RouteSchedule, Assignment


class DataLoader:
    def __init__(self, data_folder: str = "data"):
        self.data_folder = data_folder
        self.drivers: List[Driver] = []
        self.schedules: List[RouteSchedule] = []
        self.assignments: List[Assignment] = []

    def load_all(self):
        print("--- НАЧАЛО ЗАГРУЗКИ ---")
        self._load_drivers()
        self._load_schedules()
        self._load_assignments()
        self._link_drivers_to_routes()
        print("--- ЗАГРУЗКА ЗАВЕРШЕНА ---")

    def _load_drivers(self):
        path = os.path.join(self.data_folder, "drivers.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

                # 1. Если это словарь и в нем есть ключ "drivers" -> берем список оттуда
                if isinstance(raw_data, dict) and "drivers" in raw_data:
                    drivers_list = raw_data["drivers"]
                    print(f"Загружаем данные за: {raw_data.get('month')} {raw_data.get('year')}")

                # # 2. Если это просто список (старый формат) -> берем как есть
                # elif isinstance(raw_data, list):
                #     drivers_list = raw_data
                #
                # # 3. Если это одиночный объект без ключа drivers (на всякий случай)
                # else:
                #     drivers_list = [raw_data]

                self.drivers = [Driver(**d) for d in drivers_list]

            print(f"Табель: {len(self.drivers)} водителей")
        except Exception as e:
            # Добавил вывод типа ошибки, чтобы понятнее было
            print(f"Ошибка drivers.json: {type(e).__name__}: {e}")

    def _load_schedules(self):
        path = os.path.join(self.data_folder, "schedule.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict): data = [data]
                self.schedules = [RouteSchedule(**s) for s in data]
            print(f"Расписание: {len(self.schedules)} маршрутов")
        except Exception as e:
            print(f"Ошибка schedule.json: {e}")

    def _load_assignments(self):
        path = os.path.join(self.data_folder, "assignments.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assignments = [Assignment(**a) for a in data]
            print(f"Закрепления: {len(self.assignments)} связей")
        except FileNotFoundError:
            print("Файл assignments.json не найден (пропускаем)")

    def _link_drivers_to_routes(self):
        for assign in self.assignments:
            driver = next((d for d in self.drivers if int(d.id) == int(assign.driver_id)), None)
            if driver:
                driver.assigned_route_number = assign.route_number
