import json
import os
from typing import List
from src.prepare_data.models import Driver, RouteSchedule, Assignment, Absence
from datetime import datetime


class DataLoader:
    def __init__(self, data_folder: str = "data"):
        self.data_folder = data_folder
        self.drivers: List[Driver] = []
        self.schedules: List[RouteSchedule] = []
        self.assignments: List[Assignment] = []
        self.absences: List[Absence] = []

    def load_all(self):
        print("--- НАЧАЛО ЗАГРУЗКИ ---")
        self._load_drivers()
        self._load_schedules()
        self._load_assignments()                # загрузка закреплений
        self._link_drivers_to_routes()          # применение связи водитель <-> маршрут
        self._load_absences()
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

                    print(f"   📄 {filename}: Загружен {month_name} {year} ({count} водителей)")

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
        """
        Загружает сырые данные из assignmemts.json,
        заполняет список связей водитель <-> маршрут self.assignments
        """
        path = os.path.join(self.data_folder, "assignments.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assignments = [Assignment(**a) for a in data]
            print(f"Закрепления: {len(self.assignments)} связей")
        except FileNotFoundError:
            print("Файл assignments.json не найден (пропускаем)")

    def _link_drivers_to_routes(self):
        """
        Устанавливает связи: находит водителя по driver_id и приписывает ему assigned_route_number
        Данные берет из self.assignments и self.drivers
        Модифицирует атрибуты объектов Driver
        """
        for assign in self.assignments:
            # Ищем водителей по ID
            target_drivers = [d for d in self.drivers if int(d.id) == int(assign.driver_id)]
            for d in target_drivers:
                # ВАЖНО: Присваиваем номер маршрута как СТРОКУ
                d.assigned_route_number = str(assign.route_number)


    def _load_absences(self):
        """Загружает больничные и отпуска"""
        absences_path = "data/absences.json"
        self.absences = []

        if not os.path.exists(absences_path):
            print("Файл absences.json не найден (пропускаем)")
            return

        try:
            with open(absences_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data.get("absences", []):
                self.absences.append({
                    "driver_id": str(item["driver_id"]),
                    "type": item["type"],
                    "from": datetime.strptime(item["from"], "%Y-%m-%d").date(),
                    "to": datetime.strptime(item["to"], "%Y-%m-%d").date(),
                    "comment": item.get("comment", "")
                })
            print(f"Загружено отсутствий: {len(self.absences)}")
        except Exception as e:
            print(f"Ошибка загрузки absences.json: {e}")
