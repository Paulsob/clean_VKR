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
        # Путь к папке с JSON-ами месяцев
        drivers_dir = os.path.join(self.data_folder, "drivers_json")

        # Проверяем, существует ли папка
        if not os.path.exists(drivers_dir):
            print(f"Ошибка: Папка {drivers_dir} не найдена!")
            return

        print(f"Сканирую папку: {drivers_dir} ...")

        # Получаем список всех файлов в папке
        files = [f for f in os.listdir(drivers_dir) if f.endswith('.json')]

        if not files:
            print("В папке нет JSON файлов!")
            return

        self.drivers = []

        for filename in files:
            filepath = os.path.join(drivers_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                    # Ожидаем структуру: { "month": "...", "drivers": [...] }
                    month_name = data.get("month", "Unknown")
                    year = data.get("year", "Unknown")
                    drivers_list = data.get("drivers", [])

                    # Превращаем в объекты и добавляем в общий список
                    count = 0
                    for d_dict in drivers_list:
                        # ВАЖНО: обрабатываем случай, если ID написан как "0009" (строка) или 9 (число)
                        # Pydantic сам попытается привести к int, если в модели int
                        driver = Driver(**d_dict)
                        driver.month = month_name  # Прописываем месяц
                        self.drivers.append(driver)
                        count += 1

                    print(f"   📄 {filename}: Загружен {month_name} {year} ({count} вод.)")

            except json.JSONDecodeError as e:
                print(f"Ошибка JSON в файле {filename}: {e}")
                print("(Проверь, нет ли у тебя чисел вида 0009 без кавычек?)")
            except Exception as e:
                print(f"Ошибка чтения {filename}: {e}")

        print(f"Всего загружено водителей (сумма по всем месяцам): {len(self.drivers)}")

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
