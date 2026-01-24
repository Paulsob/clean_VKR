import json
import os
from typing import List
from src.prepare_data.models import Driver, RouteSchedule, Assignment, Absence
from src.logger import get_logger
from datetime import datetime

# Инициализируем логгер для этого модуля
logger = get_logger(__name__)


class DataLoader:
    def __init__(self, data_folder: str = "data"):
        self.data_folder = data_folder
        self.drivers: List[Driver] = []
        self.schedules: List[RouteSchedule] = []
        self.assignments: List[Assignment] = []
        self.absences: List[Absence] = []

    def load_all(self):
        logger.info("Начинаем загрузку данных")
        self._load_drivers()
        self._load_schedules()
        self._load_assignments()                # загрузка закреплений
        self._link_drivers_to_routes()          # применение связи водитель <-> маршрут
        self._load_absences()
        logger.info("Загрузка данных завершена")

    def _load_drivers(self):
        # Путь к папке с JSON-ами месяцев
        drivers_dir = os.path.join(self.data_folder, "drivers_json")

        # Проверяем, существует ли папка
        if not os.path.exists(drivers_dir):
            logger.error(f"Папка водителей не найдена: {drivers_dir}")
            return

        logger.info(f"Сканирую папку водителей: {drivers_dir}")

        # Получаем список всех файлов в папке
        files = [f for f in os.listdir(drivers_dir) if f.endswith('.json')]

        if not files:
            logger.warning("В папке нет JSON файлов с водителями")
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

                    logger.debug(f"Загружен файл {filename}: {month_name} {year} ({count} водителей)")

            except json.JSONDecodeError as e:
                logger.error(f"Ошибка JSON в файле {filename}: {e}")
                logger.warning("Проверьте, нет ли чисел вида 0009 без кавычек")
            except Exception as e:
                logger.error(f"Ошибка чтения файла {filename}: {e}")

        logger.info(f"Всего загружено водителей: {len(self.drivers)}")

    def _load_schedules(self):
        path = os.path.join(self.data_folder, "schedule.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict): data = [data]
                self.schedules = [RouteSchedule(**s) for s in data]
            logger.info(f"Загружено расписаний: {len(self.schedules)} маршрутов")
        except Exception as e:
            logger.error(f"Ошибка загрузки schedule.json: {e}")

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
            logger.info(f"Загружено закреплений: {len(self.assignments)} связей")
        except FileNotFoundError:
            logger.warning("Файл assignments.json не найден (пропускаем)")

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
            logger.warning("Файл absences.json не найден (пропускаем)")
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
            logger.info(f"Загружено отсутствий: {len(self.absences)}")
        except Exception as e:
            logger.error(f"Ошибка загрузки absences.json: {e}")
