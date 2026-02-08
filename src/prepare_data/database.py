import json
import os
from typing import List
from datetime import datetime

from src.prepare_data.models import Driver, RouteSchedule, Assignment, Absence
from src.logger import get_logger
from src.config import DATA_DIR, USE_SYNTHETIC_DATA, SELECTED_PATTERN, PROCESS_ALL_ROUTES, SELECTED_ROUTE

logger = get_logger(__name__)


class DataLoader:
    def __init__(self, data_folder: str = None):
        self.data_folder = data_folder if data_folder else DATA_DIR

        if not os.path.exists(self.data_folder):
            raise FileNotFoundError(f"Папка с данными не найдена: {self.data_folder}")

        self.drivers: List[Driver] = []
        self.schedules: List[RouteSchedule] = []
        self.assignments: List[Assignment] = []
        self.absences: List[Absence] = []

    def load_all(self):
        logger.info(f"Начинаем загрузку данных. Режим: {'SYNTHETIC' if USE_SYNTHETIC_DATA else 'REAL'}")
        self._load_drivers()
        self._load_schedules()
        self._load_assignments()
        self._link_drivers_to_routes()
        self._load_absences()
        logger.info("Загрузка данных завершена")

    def _load_drivers(self):
        """
        Загружает водителей в зависимости от режима конфигурации.
        """
        drivers_base_dir = os.path.join(self.data_folder, "drivers_json")

        if not os.path.exists(drivers_base_dir):
            logger.error(f"Папка водителей не найдена: {drivers_base_dir}")
            return

        json_files_to_load = []

        if USE_SYNTHETIC_DATA:
            if SELECTED_PATTERN and SELECTED_PATTERN.lower() != "all":
                target_folder = os.path.join(drivers_base_dir, SELECTED_PATTERN)
                if os.path.exists(target_folder):
                    folders_to_scan = [target_folder]
                    logger.info(f"[SYNTHETIC] Загружаю только график: {SELECTED_PATTERN}")
                else:
                    logger.error(f"Папка для графика {SELECTED_PATTERN} не найдена в {drivers_base_dir}")
                    return
            else:
                logger.warning("[SYNTHETIC] Выбран режим ALL - загружаю все графики в кучу!")
                folders_to_scan = [os.path.join(drivers_base_dir, d) for d in os.listdir(drivers_base_dir) if
                                   os.path.isdir(os.path.join(drivers_base_dir, d))]

            # --- ИСПРАВЛЕНИЕ: Сканируем все .json файлы в папке ---
            for folder_path in folders_to_scan:
                found_any = False
                for fname in os.listdir(folder_path):
                    if fname.endswith(".json"):
                        full_path = os.path.join(folder_path, fname)
                        json_files_to_load.append(full_path)
                        found_any = True

                if not found_any:
                    logger.warning(f"В папке {folder_path} не найдено .json файлов водителей.")
            # ------------------------------------------------------

        else:
            logger.info(f"[REAL] Сканирую файлы месяцев в {drivers_base_dir}")
            for f_name in os.listdir(drivers_base_dir):
                if f_name.endswith('.json'):
                    json_files_to_load.append(os.path.join(drivers_base_dir, f_name))

        if not json_files_to_load:
            logger.warning("Не найдено файлов водителей для загрузки.")
            return

        # Сортируем файлы, чтобы Январь грузился раньше Февраля
        json_files_to_load.sort()
        logger.info(f"Найдено файлов для загрузки: {len(json_files_to_load)}")

        self.drivers = []
        total_loaded = 0

        # Словарь для объединения данных водителей из разных месяцев
        # Ключ: tab_number (или id), Значение: объект Driver
        drivers_map = {}

        for filepath in json_files_to_load:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    month_name = data.get("month", "Unknown")
                    drivers_list = data.get("drivers", [])

                    # Логируем, какой файл грузим
                    logger.debug(f"Грузим файл: {os.path.basename(filepath)} ({month_name})")

                    count = 0
                    for d_dict in drivers_list:
                        try:
                            # Пытаемся получить ID
                            d_id = str(d_dict.get('tab_number') or d_dict.get('id'))

                            # Если водитель уже есть - обновляем его расписание
                            if d_id in drivers_map:
                                existing_driver = drivers_map[d_id]
                                new_days = d_dict.get('days', [])  # это список словарей [{"day": 1, "value": "1"}]

                                # Преобразуем новый список дней в словарь {day: value}
                                new_schedule = {}
                                for day_item in new_days:
                                    if isinstance(day_item, dict):
                                        # Используем строку для ключа
                                        new_schedule[str(day_item['day'])] = str(day_item['value'])

                                # ВАЖНО: Тут нужно решить, как объединять.
                                # Если Driver.schedule это словарь, просто делаем update.
                                # Но так как у тебя Driver.schedule это поле Pydantic, нужно понять его тип.
                                # Предположим, что модель Driver умеет принимать список days при init.
                                # Здесь мы просто обновляем существующий объект.

                                # Проще всего: если месяц разный, мы грузим их как РАЗНЫЕ объекты в список?
                                # Нет, DataLoader обычно должен вернуть список уникальных водителей.
                                # Но твоя симуляция может работать с "водителем в январе" и "водителем в феврале".

                                # Если Driver.month - это одно поле, то один объект Driver не может быть одновременно и в Январе и в Феврале.
                                # Поэтому: грузим их как отдельные объекты.

                                driver = Driver(**d_dict)
                                driver.month = month_name
                                self.drivers.append(driver)
                                count += 1

                            else:
                                driver = Driver(**d_dict)
                                driver.month = month_name
                                self.drivers.append(driver)
                                # Запоминаем ID, чтобы знать, встречали ли мы его
                                drivers_map[d_id] = driver
                                count += 1
                        except Exception as ex:
                            # logger.warning(f"Ошибка парсинга водителя: {ex}")
                            pass
                    total_loaded += count
            except Exception as e:
                logger.error(f"Ошибка чтения {filepath}: {e}")

        logger.info(
            f"Загружено записей о водителях: {len(self.drivers)} (График: {SELECTED_PATTERN if USE_SYNTHETIC_DATA else 'Real'})")

    def _load_schedules(self):
        path = os.path.join(self.data_folder, "schedule.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict): data = [data]
                self.schedules = [RouteSchedule(**s) for s in data]
            logger.info(f"Загружены расписания для {len(self.schedules)} маршрутов")
        except Exception as e:
            logger.error(f"Ошибка загрузки schedule.json: {e}")

    def _load_assignments(self):
        path = os.path.join(self.data_folder, "assignments.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assignments = [Assignment(**a) for a in data]
            logger.info(f"Загружено закреплений: {len(self.assignments)} связей")
        except FileNotFoundError:
            if not USE_SYNTHETIC_DATA:
                logger.warning("Файл assignments.json не найден")

    def _link_drivers_to_routes(self):
        # 1. Реальные закрепления (Assignments)
        for assign in self.assignments:
            target_drivers = [d for d in self.drivers if int(d.id) == int(assign.driver_id)]
            for d in target_drivers:
                d.assigned_route_number = str(assign.route_number)

        # 2. Логика СИНТЕТИКИ (Round Robin)
        if USE_SYNTHETIC_DATA:
            logger.info("[SYNTHETIC] Распределяем водителей по маршрутам...")

            # Определяем список активных маршрутов
            active_routes = []
            if PROCESS_ALL_ROUTES and self.schedules:
                active_routes = sorted(list(set(str(s.route_number) for s in self.schedules)))
            elif SELECTED_ROUTE:
                active_routes = [str(SELECTED_ROUTE)]

            if not active_routes:
                logger.warning("Нет маршрутов для распределения!")
                return

            # Берем только тех, кто еще без маршрута
            unassigned_drivers = [d for d in self.drivers if not d.assigned_route_number]

            # ВАЖНО: Сортируем их, чтобы распределение было стабильным при каждом запуске
            unassigned_drivers.sort(key=lambda x: int(x.id))

            # Раздаем как карты: 1-й маршруту А, 2-й маршруту Б...
            for i, driver in enumerate(unassigned_drivers):
                target_route = active_routes[i % len(active_routes)]
                driver.assigned_route_number = target_route

            logger.info(f"Маршруты ({len(active_routes)} шт): {active_routes}")
            logger.info(f"Водителей ({len(unassigned_drivers)} шт) распределено равномерно.")
            logger.info(f"(~{len(unassigned_drivers) // len(active_routes)} водителей на маршрут)")

    def _load_absences(self):
        absences_path = os.path.join(self.data_folder, "absences.json")

        self.absences = []

        if not os.path.exists(absences_path):
            if not USE_SYNTHETIC_DATA:
                logger.warning(f"Файл absences.json не найден: {absences_path}")
            return

        try:
            with open(absences_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

                if isinstance(raw_data, list):
                    data_list = raw_data
                else:
                    data_list = raw_data.get("absences", [])

            for item in data_list:
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
