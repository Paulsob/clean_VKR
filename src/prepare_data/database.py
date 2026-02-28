import json
import os
from typing import List, Dict
from datetime import datetime, timedelta

from src.prepare_data.models import Driver, RouteSchedule, Assignment, Absence
from src.logger import get_logger
import src.config as config

logger = get_logger(__name__)


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
        """Добавляет ошибку в статистику."""
        error_msg = f"{context}: {str(error)}"
        if filepath:
            error_msg = f"{filepath} - {error_msg}"
        self.errors.append(error_msg)
        logger.error(error_msg)
    
    def log_summary(self):
        """Выводит итоговую статистику загрузки."""
        logger.info("=" * 60)
        logger.info("СТАТИСТИКА ЗАГРУЗКИ ДАННЫХ")
        logger.info(f"Водители: {self.drivers_loaded} загружено, {self.drivers_failed} пропущено")
        logger.info(f"Расписания: {self.schedules_loaded}")
        logger.info(f"Закрепления: {self.assignments_loaded}")
        logger.info(f"Отсутствия: {self.absences_loaded}")
        logger.info(f"Файлы: {self.files_processed} обработано, {self.files_failed} с ошибками")
        
        if self.errors:
            logger.warning(f"Обнаружено {len(self.errors)} ошибок при загрузке:")
            for i, err in enumerate(self.errors[:5], 1):  # Показываем первые 5
                logger.warning(f"  {i}. {err}")
            if len(self.errors) > 5:
                logger.warning(f"  ... и еще {len(self.errors) - 5} ошибок")
        else:
            logger.info("✓ Загрузка завершена без ошибок")
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

        # Словарь для хранения рассчитанных норм: { "driver_id": float_hours }
        self.driver_norms: Dict[str, float] = {}
        
        # Статистика загрузки
        self.stats = LoadingStats()

    def load_all(self):
        logger.info(f"Начинаем загрузку данных. Режим: {'SYNTHETIC' if config.USE_SYNTHETIC_DATA else 'REAL'}")
        self._load_drivers()
        self._load_schedules()
        self._load_assignments()
        self._link_drivers_to_routes()
        self._load_absences()

        # НОВЫЙ ШАГ: Расчет норм выработки
        self._calculate_and_save_norms()

        # Выводим статистику
        self.stats.log_summary()
        logger.info("Загрузка данных завершена")

    def _load_drivers(self):
        """Загружает водителей в зависимости от режима конфигурации."""
        drivers_base_dir = os.path.join(config.DATA_DIR, "drivers_json")

        if not os.path.exists(drivers_base_dir):
            logger.error(f"Папка водителей не найдена: {drivers_base_dir}")
            return

        json_files_to_load = []

        if config.USE_SYNTHETIC_DATA:
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
                try:
                    for fname in os.listdir(folder_path):
                        if fname.endswith(".json"):
                            json_files_to_load.append(os.path.join(folder_path, fname))
                except OSError:
                    pass
        else:
            logger.info(f"[REAL] Сканирую файлы месяцев в {drivers_base_dir}")
            for f_name in os.listdir(drivers_base_dir):
                if f_name.endswith('.json'):
                    json_files_to_load.append(os.path.join(drivers_base_dir, f_name))

        if not json_files_to_load:
            logger.warning("Не найдено файлов водителей для загрузки.")
            return

        json_files_to_load.sort()
        self.drivers = []

        for filepath in json_files_to_load:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    month_name = data.get("month", "Unknown")
                    drivers_list = data.get("drivers", [])

                    for d_dict in drivers_list:
                        try:
                            driver = Driver(**d_dict)
                            driver.month = month_name
                            self.drivers.append(driver)
                            self.stats.drivers_loaded += 1
                        except Exception as e:
                            self.stats.drivers_failed += 1
                            self.stats.add_error(
                                f"Ошибка парсинга водителя (ID: {d_dict.get('tab_number', 'unknown')})",
                                e,
                                filepath
                            )
                
                self.stats.files_processed += 1
                
            except json.JSONDecodeError as e:
                self.stats.files_failed += 1
                self.stats.add_error("Ошибка парсинга JSON", e, filepath)
            except Exception as e:
                self.stats.files_failed += 1
                self.stats.add_error("Ошибка чтения файла", e, filepath)

        logger.info(f"Загружено записей о водителях: {len(self.drivers)}")

    def _load_schedules(self):
        path = os.path.join(self.data_folder, "schedule.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict): 
                    data = [data]
                
                for schedule_dict in data:
                    try:
                        schedule = RouteSchedule(**schedule_dict)
                        self.schedules.append(schedule)
                        self.stats.schedules_loaded += 1
                    except Exception as e:
                        route_num = schedule_dict.get("маршрут", schedule_dict.get("route_number", "unknown"))
                        self.stats.add_error(
                            f"Ошибка парсинга расписания маршрута {route_num}",
                            e,
                            path
                        )
                
            logger.info(f"Загружены расписания для {len(self.schedules)} маршрутов")
        except FileNotFoundError:
            self.stats.add_error("Файл schedule.json не найден", FileNotFoundError(), path)
        except json.JSONDecodeError as e:
            self.stats.add_error("Ошибка парсинга JSON", e, path)
        except Exception as e:
            self.stats.add_error("Ошибка загрузки расписаний", e, path)

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
        # 1. Реальные закрепления
        for assign in self.assignments:
            target_drivers = [d for d in self.drivers if int(d.id) == int(assign.driver_id)]
            for d in target_drivers:
                d.assigned_route_number = str(assign.route_number)

        # 2. Синтетика
        if config.USE_SYNTHETIC_DATA:
            logger.info("[SYNTHETIC] Распределяем водителей по маршрутам...")
            active_routes = []
            if config.PROCESS_ALL_ROUTES and self.schedules:
                active_routes = sorted(list(set(str(s.route_number) for s in self.schedules)))
            elif config.SELECTED_ROUTE:
                active_routes = [str(config.SELECTED_ROUTE)]

            if not active_routes:
                return

            unassigned_drivers = [d for d in self.drivers if not d.assigned_route_number]
            unassigned_drivers.sort(key=lambda x: int(x.id) if str(x.id).isdigit() else x.id)

            if not unassigned_drivers:
                return

            # Веса маршрутов
            route_weights = {}
            total_weight = 0
            for r_num in active_routes:
                r_schedules = [s for s in self.schedules if str(s.route_number) == r_num]
                max_shifts = 0
                for sched in r_schedules:
                    shifts_in_day = 0
                    for tram in sched.trams:
                        if tram.shift_1: shifts_in_day += 1
                        if tram.shift_2: shifts_in_day += 1
                    if shifts_in_day > max_shifts: max_shifts = shifts_in_day

                weight = max_shifts if max_shifts > 0 else 1
                route_weights[r_num] = weight
                total_weight += weight

            # Распределение
            total_drivers = len(unassigned_drivers)
            current_driver_idx = 0
            sorted_routes = sorted(active_routes)

            for i, r_num in enumerate(sorted_routes):
                if i == len(sorted_routes) - 1:
                    count_to_assign = total_drivers - current_driver_idx
                else:
                    share = route_weights[r_num] / total_weight
                    count_to_assign = int(total_drivers * share)

                for _ in range(count_to_assign):
                    if current_driver_idx < total_drivers:
                        unassigned_drivers[current_driver_idx].assigned_route_number = r_num
                        current_driver_idx += 1

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