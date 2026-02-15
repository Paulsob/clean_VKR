import json
import os
from typing import List
from datetime import datetime

from src.prepare_data.models import Driver, RouteSchedule, Assignment, Absence
from src.logger import get_logger
import src.config as config
from src.prepare_data.models import Driver, RouteSchedule, Assignment, Absence
from src.logger import get_logger

logger = get_logger(__name__)


class DataLoader:
    def __init__(self, data_folder: str = None):
        self.data_folder = data_folder if data_folder else config.DATA_DIR

        if not os.path.exists(self.data_folder):
            raise FileNotFoundError(f"Папка с данными не найдена: {self.data_folder}")

        self.drivers: List[Driver] = []
        self.schedules: List[RouteSchedule] = []
        self.assignments: List[Assignment] = []
        self.absences: List[Absence] = []

    def load_all(self):
        logger.info(f"Начинаем загрузку данных. Режим: {'SYNTHETIC' if config.USE_SYNTHETIC_DATA else 'REAL'}")
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
        # Используем config.DATA_DIR вместо DATA_DIR
        drivers_base_dir = os.path.join(config.DATA_DIR, "drivers_json")

        if not os.path.exists(drivers_base_dir):
            logger.error(f"Папка водителей не найдена: {drivers_base_dir}")
            return

        json_files_to_load = []

        # Используем config.USE_SYNTHETIC_DATA
        if config.USE_SYNTHETIC_DATA:
            # Используем config.SELECTED_PATTERN (ДИНАМИЧЕСКИ!)
            pattern = config.SELECTED_PATTERN

            if pattern and pattern.lower() != "all":
                target_folder = os.path.join(drivers_base_dir, pattern)
                if os.path.exists(target_folder):
                    folders_to_scan = [target_folder]
                    logger.info(f"[SYNTHETIC] Загружаю только график: {pattern}")
                else:
                    logger.error(f"Папка для графика {pattern} не найдена в {drivers_base_dir}")
                    return
            else:
                logger.warning("[SYNTHETIC] Выбран режим ALL - загружаю все графики в кучу!")
                folders_to_scan = [os.path.join(drivers_base_dir, d) for d in os.listdir(drivers_base_dir) if
                                   os.path.isdir(os.path.join(drivers_base_dir, d))]

            for folder_path in folders_to_scan:
                found_any = False
                try:
                    for fname in os.listdir(folder_path):
                        if fname.endswith(".json"):
                            full_path = os.path.join(folder_path, fname)
                            json_files_to_load.append(full_path)
                            found_any = True
                except OSError:
                    pass

                if not found_any:
                    logger.warning(f"В папке {folder_path} не найдено .json файлов водителей.")

        else:
            logger.info(f"[REAL] Сканирую файлы месяцев в {drivers_base_dir}")
            for f_name in os.listdir(drivers_base_dir):
                if f_name.endswith('.json'):
                    json_files_to_load.append(os.path.join(drivers_base_dir, f_name))

        if not json_files_to_load:
            logger.warning("Не найдено файлов водителей для загрузки.")
            return

        json_files_to_load.sort()
        logger.info(f"Найдено файлов для загрузки: {len(json_files_to_load)}")

        self.drivers = []
        drivers_map = {}  # Для дедупликации, если нужно

        for filepath in json_files_to_load:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    month_name = data.get("month", "Unknown")
                    drivers_list = data.get("drivers", [])

                    for d_dict in drivers_list:
                        try:
                            # Грузим как есть
                            driver = Driver(**d_dict)
                            driver.month = month_name
                            self.drivers.append(driver)
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Ошибка чтения {filepath}: {e}")

        logger.info(
            f"Загружено записей о водителях: {len(self.drivers)} (График: {config.SELECTED_PATTERN if config.USE_SYNTHETIC_DATA else 'Real'})")


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
            if not config.USE_SYNTHETIC_DATA:
                logger.warning("Файл assignments.json не найден")

    def _link_drivers_to_routes(self):
        # 1. Реальные закрепления (Assignments) - если есть файл, используем его
        for assign in self.assignments:
            target_drivers = [d for d in self.drivers if int(d.id) == int(assign.driver_id)]
            for d in target_drivers:
                d.assigned_route_number = str(assign.route_number)

        # 2. Логика СИНТЕТИКИ (Пропорциональное распределение)
        if config.USE_SYNTHETIC_DATA:
            logger.info("[SYNTHETIC] Распределяем водителей по маршрутам (Пропорционально нагрузке)...")

            # Определяем список активных маршрутов
            active_routes = []
            if config.PROCESS_ALL_ROUTES and self.schedules:
                active_routes = sorted(list(set(str(s.route_number) for s in self.schedules)))
            elif config.SELECTED_ROUTE:
                active_routes = [str(config.SELECTED_ROUTE)]

            if not active_routes:
                logger.warning("Нет маршрутов для распределения!")
                return

            # Берем только тех, кто еще без маршрута
            unassigned_drivers = [d for d in self.drivers if not d.assigned_route_number]
            unassigned_drivers.sort(key=lambda x: int(x.id))  # Стабильная сортировка

            if not unassigned_drivers:
                return

            # --- ЭТАП 1: Подсчет веса (нагрузки) каждого маршрута ---
            route_weights = {}
            total_weight = 0

            for r_num in active_routes:
                # Ищем все расписания для этого маршрута
                r_schedules = [s for s in self.schedules if str(s.route_number) == r_num]

                if not r_schedules:
                    # Если расписания нет, даем минимальный вес
                    weight = 1
                else:
                    # Находим МАКСИМАЛЬНОЕ кол-во смен, которое бывает на этом маршруте
                    # (чтобы покрыть потребность в самый загруженный день, например, Будни)
                    max_shifts_count = 0
                    for sched in r_schedules:
                        shifts_in_day = 0
                        for tram in sched.trams:
                            # Считаем активные смены
                            if tram.shift_1: shifts_in_day += 1
                            if tram.shift_2: shifts_in_day += 1

                        if shifts_in_day > max_shifts_count:
                            max_shifts_count = shifts_in_day

                    weight = max_shifts_count if max_shifts_count > 0 else 1

                route_weights[r_num] = weight
                total_weight += weight

            logger.info(f"Веса маршрутов (кол-во смен в пике): {route_weights}")

            # --- ЭТАП 2: Распределение водителей ---
            total_drivers = len(unassigned_drivers)
            current_driver_idx = 0

            # Сортируем маршруты, чтобы распределение было детерминированным
            # (но вообще порядок не так важен при пропорциях)
            sorted_routes = sorted(active_routes)

            assigned_stats = {}

            for i, r_num in enumerate(sorted_routes):
                weight = route_weights[r_num]

                # Доля водителей для этого маршрута
                # Если это последний маршрут в списке, отдаем ему всех оставшихся (чтобы не потерять из-за округления)
                if i == len(sorted_routes) - 1:
                    count_to_assign = total_drivers - current_driver_idx
                else:
                    share = weight / total_weight
                    count_to_assign = int(total_drivers * share)

                # Назначаем
                for _ in range(count_to_assign):
                    if current_driver_idx < total_drivers:
                        unassigned_drivers[current_driver_idx].assigned_route_number = r_num
                        current_driver_idx += 1

                assigned_stats[r_num] = count_to_assign

            logger.info(f"Итоговое распределение водителей: {assigned_stats}")

            # Проверка на потерянных (не должно быть)
            if current_driver_idx < total_drivers:
                logger.warning(
                    f"Осталось {total_drivers - current_driver_idx} нераспределенных водителей! Докидываем в последний маршрут.")
                last_route = sorted_routes[-1]
                while current_driver_idx < total_drivers:
                    unassigned_drivers[current_driver_idx].assigned_route_number = last_route
                    current_driver_idx += 1

    def _load_absences(self):
        absences_path = os.path.join(self.data_folder, "absences.json")

        self.absences = []

        if not os.path.exists(absences_path):
            if not config.USE_SYNTHETIC_DATA:
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
