import json
import os
from typing import List, Dict
from datetime import datetime
from src.prepare_data.models import Driver, RouteSchedule, Assignment, Absence
from src.logger import get_logger
import src.config as config

logger = get_logger(__name__)

# КАРТА СМЕЩЕНИЙ ID (чтобы ID оставались int, но были уникальными)
# 4x2: 1..9999
# 5x2: 10001..19999
# 5x2_holidays: 20001..29999
PATTERN_OFFSETS = {
    "4x2": 0,
    "5x2": 10000,
    "5х2_holiday": 20000,
    "3x2x3x1": 30000
}


class LoadingStats:
    """Статистика загрузки данных для отчетности."""

    def __init__(self):
        self.drivers_loaded = 0
        self.drivers_failed = 0
        self.schedules_loaded = 0
        self.assignments_loaded = 0
        self.absences_loaded = 0
        self.files_processed = 0
        self.files_failed = 0
        self.errors = []

    def add_error(self, context: str, error: Exception, filepath: str = None):
        error_msg = f"{context}: {str(error)}"
        if filepath:
            error_msg = f"{filepath} - {error_msg}"
        self.errors.append(error_msg)
        logger.error(error_msg)

    def log_summary(self):
        logger.info("=" * 60)
        logger.info("СТАТИСТИКА ЗАГРУЗКИ ДАННЫХ")
        logger.info(f"Водители: {self.drivers_loaded} загружено, {self.drivers_failed} пропущено")
        logger.info(f"Расписания: {self.schedules_loaded}")
        logger.info("=" * 60)


class DataLoader:
    def __init__(self, data_folder: str = None):
        self.data_folder = data_folder if data_folder else config.DATA_DIR
        if not os.path.exists(self.data_folder):
            raise FileNotFoundError(f"Папка с данными не найдена: {self.data_folder}")

        self.drivers: List[Driver] = []
        self.schedules: List[RouteSchedule] = []
        self.assignments: List[Assignment] = []
        self.absences: List[Absence] = []
        self.driver_norms: Dict[str, float] = {}
        self.stats = LoadingStats()

    def load_all(self):
        logger.info(f"Начинаем загрузку данных. Режим: {'SYNTHETIC' if config.USE_SYNTHETIC_DATA else 'REAL'}")
        self._load_drivers()
        self._load_schedules()
        self._load_assignments()
        self._link_drivers_to_routes()
        self._load_absences()
        self._calculate_and_save_norms()
        self.stats.log_summary()

    def _load_drivers(self):
        """Загружает водителей, добавляя математическое смещение к ID для уникальности."""
        drivers_base_dir = os.path.join(config.DATA_DIR, "drivers_json")
        if not os.path.exists(drivers_base_dir):
            logger.error(f"Папка водителей не найдена: {drivers_base_dir}")
            return

        json_files_map = []  # [(path, pattern_name)]

        if config.USE_SYNTHETIC_DATA:
            patterns = config.INPUT_PATTERNS
            logger.info(f"[SYNTHETIC] Загружаю графики: {patterns}")

            for pattern in patterns:
                folder_path = os.path.join(drivers_base_dir, pattern)
                if os.path.exists(folder_path):
                    for fname in os.listdir(folder_path):
                        if fname.endswith(".json"):
                            full_path = os.path.join(folder_path, fname)
                            json_files_map.append((full_path, pattern))
                else:
                    logger.warning(f"Папка графика {pattern} не найдена в {drivers_base_dir}")
        else:
            for fname in os.listdir(drivers_base_dir):
                if fname.endswith(".json"):
                    json_files_map.append((os.path.join(drivers_base_dir, fname), "real"))

        self.drivers = []
        for filepath, pattern_name in json_files_map:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    month_name = data.get("month", "Unknown")
                    drivers_list = data.get("drivers", [])

                    for d_dict in drivers_list:
                        try:
                            # --- УНИКАЛИЗАЦИЯ ID (Через смещение int) ---
                            original_id = int(d_dict.get("tab_number") or d_dict.get("id"))

                            if config.USE_SYNTHETIC_DATA:
                                # Получаем смещение (0 для 4x2, 10000 для 5x2 и т.д.)
                                # Если паттерна нет в списке, берем большое число 90000
                                offset = PATTERN_OFFSETS.get(pattern_name, 90000)
                                unique_id = original_id + offset
                            else:
                                unique_id = original_id

                            # Обновляем словарь перед созданием объекта (чтобы Pydantic не ругался)
                            d_dict["tab_number"] = unique_id
                            d_dict["id"] = unique_id

                            # Создаем объект
                            driver = Driver(**d_dict)
                            driver.month = month_name

                            # ВАЖНО: Принудительно вешаем метку графика на объект
                            # Pydantic может ее не пропустить в конструкторе, поэтому делаем setattr
                            setattr(driver, "schedule_pattern", pattern_name)

                            self.drivers.append(driver)
                            self.stats.drivers_loaded += 1
                        except Exception as e:
                            self.stats.drivers_failed += 1
                            # self.stats.add_error(f"Ошибка парсинга водителя {d_dict.get('tab_number')}", e, filepath)
                            # Логируем только критичные ошибки, чтобы не спамить консоль
                            if self.stats.drivers_failed <= 5:
                                logger.warning(f"Ошибка водителя: {e}")

                self.stats.files_processed += 1
            except Exception as e:
                self.stats.files_failed += 1
                self.stats.add_error("Ошибка чтения файла", e, filepath)

    def _load_schedules(self):
        path = os.path.join(self.data_folder, "schedule.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict): data = [data]
            for s_dict in data:
                self.schedules.append(RouteSchedule(**s_dict))
                self.stats.schedules_loaded += 1
        except Exception as e:
            self.stats.add_error("Load Schedules", e)


    def _load_assignments(self):
        path = os.path.join(self.data_folder, "assignments.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for assign_dict in data:
                    try:
                        assignment = Assignment(**assign_dict)
                        self.assignments.append(assignment)
                        self.stats.assignments_loaded += 1
                    except Exception as e:
                        driver_id = assign_dict.get("driver_id", "unknown")
                        self.stats.add_error(
                            f"Ошибка парсинга закрепления водителя {driver_id}",
                            e,
                            path
                        )

            logger.info(f"Загружено закреплений: {len(self.assignments)} связей")
        except FileNotFoundError:
            if not config.USE_SYNTHETIC_DATA:
                logger.warning("Файл assignments.json не найден")
        except json.JSONDecodeError as e:
            self.stats.add_error("Ошибка парсинга JSON", e, path)
        except Exception as e:
            self.stats.add_error("Ошибка загрузки закреплений", e, path)

    def _link_drivers_to_routes(self):
        if not config.USE_SYNTHETIC_DATA: return
        active_routes = [str(config.SELECTED_ROUTE)] if config.SELECTED_ROUTE else []
        if config.PROCESS_ALL_ROUTES and self.schedules:
            active_routes = sorted(list(set(str(s.route_number) for s in self.schedules)))
        if not active_routes: return

        unassigned = [d for d in self.drivers if not getattr(d, 'assigned_route_number', None)]
        # Сортировка по числовому ID
        unassigned.sort(key=lambda x: int(x.id))

        import math
        chunk_size = math.ceil(len(unassigned) / len(active_routes))
        for i, r_num in enumerate(active_routes):
            chunk = unassigned[i*chunk_size : (i+1)*chunk_size]
            for d in chunk:
                d.assigned_route_number = r_num

    def _load_absences(self):
        absences_path = os.path.join(self.data_folder, "absences.json")
        self.absences = []
        if not os.path.exists(absences_path):
            return

        try:
            with open(absences_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                data_list = raw_data if isinstance(raw_data, list) else raw_data.get("absences", [])

            for item in data_list:
                try:
                    self.absences.append({
                        "driver_id": str(item["driver_id"]),
                        "type": item["type"],
                        "from": datetime.strptime(item["from"], "%Y-%m-%d").date(),
                        "to": datetime.strptime(item["to"], "%Y-%m-%d").date()
                    })
                    self.stats.absences_loaded += 1
                except KeyError as e:
                    self.stats.add_error(
                        f"Отсутствует обязательное поле в записи отсутствия: {e}",
                        e,
                        absences_path
                    )
                except ValueError as e:
                    self.stats.add_error(
                        f"Ошибка парсинга даты в записи отсутствия (driver_id: {item.get('driver_id', 'unknown')})",
                        e,
                        absences_path
                    )
                except Exception as e:
                    self.stats.add_error(
                        f"Ошибка обработки записи отсутствия",
                        e,
                        absences_path
                    )

        except json.JSONDecodeError as e:
            self.stats.add_error("Ошибка парсинга JSON", e, absences_path)
        except Exception as e:
            self.stats.add_error("Ошибка загрузки отсутствий", e, absences_path)

    # =========================================================================
    # НОВЫЙ МЕТОД: РАСЧЕТ И СОХРАНЕНИЕ НОРМ
    # =========================================================================
    def _calculate_and_save_norms(self):
        """
        1. Считает среднюю длительность смены для каждого маршрута.
        2. Считает количество рабочих дней у каждого водителя (через get_status_for_day).
        3. Вычисляет норму: Дни * Ср.Длительность.
        4. Сохраняет в data/norms.json.
        """
        logger.info("Начинаем расчет норм выработки (Target Hours)...")

        # --- 1. Считаем среднюю длину смены для каждого маршрута ---
        route_stats = {}  # { "route_num": {"total_hours": X, "count": Y} }

        def parse_time(t_str):
            try:
                h, m = map(int, t_str.split(':'))
                return h * 60 + m
            except:
                return 0

        for sched in self.schedules:
            r_num = str(sched.route_number)
            if r_num not in route_stats:
                route_stats[r_num] = {"total_hours": 0, "count": 0}

            for tram in sched.trams:
                for shift in [tram.shift_1, tram.shift_2]:
                    if shift and shift.start and shift.end:
                        start_min = parse_time(shift.start)
                        end_min = parse_time(shift.end)

                        # Если смена переходит через полночь
                        if end_min < start_min:
                            end_min += 24 * 60

                        duration_hours = (end_min - start_min) / 60.0

                        # Фильтрация аномалий
                        if 2.0 < duration_hours < 14.0:
                            route_stats[r_num]["total_hours"] += duration_hours
                            route_stats[r_num]["count"] += 1

        # Вычисляем средние значения
        route_averages = {}
        for r_num, stats in route_stats.items():
            if stats["count"] > 0:
                route_averages[r_num] = round(stats["total_hours"] / stats["count"], 2)
            else:
                route_averages[r_num] = 8.0  # Дефолт

        logger.info(f"Средняя длительность смен по маршрутам: {route_averages}")

        # --- 2. Считаем норму для каждого водителя ---
        self.driver_norms = {}

        for driver in self.drivers:
            assigned_route = str(driver.assigned_route_number) if driver.assigned_route_number else "unknown"
            avg_duration = route_averages.get(assigned_route, 8.0)

            # Считаем рабочие дни, перебирая календарные дни месяца (1..31)
            work_days_count = 0

            # Проверяем дни с 1 по 31
            for day_idx in range(1, 32):
                try:
                    # Используем существующий метод модели
                    status = driver.get_status_for_day(day_idx)

                    # Логика определения рабочего дня:
                    # 1. Если статус - цифра (смена '1', '2' и т.д.)
                    # 2. Если статус - буква, означающая работу ('Р', 'Я', 'S')
                    # 3. Исключаем выходные ('В'), отпуска ('О'), больничные ('Б')
                    s_str = str(status).upper().strip()

                    if s_str.isdigit():
                        work_days_count += 1
                    elif s_str in ['Р', 'Я', 'S', 'WORK']:
                        work_days_count += 1
                    # Если статус None или 'В', ничего не делаем

                except Exception:
                    # Если день (например, 31-е февраля) не существует, метод может упасть
                    continue

            # Защита от нулевого графика (если вдруг ошибка парсинга)
            if work_days_count == 0:
                work_days_count = 21  # Стандартная пятидневка

            target_hours = round(work_days_count * avg_duration, 1)
            self.driver_norms[str(driver.id)] = target_hours

        # --- 3. Сохраняем в JSON ---
        norms_filepath = os.path.join(self.data_folder, "norms.json")
        try:
            with open(norms_filepath, "w", encoding="utf-8") as f:
                output = {
                    "meta": {
                        "generated_at": datetime.now().isoformat(),
                        "route_averages": route_averages
                    },
                    "drivers": self.driver_norms
                }
                json.dump(output, f, indent=4, ensure_ascii=False)
            logger.info(f"Нормы выработки сохранены в {norms_filepath}")
        except Exception as e:
            logger.error(f"Не удалось сохранить norms.json: {e}")