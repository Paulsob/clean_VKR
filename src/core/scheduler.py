from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple, Any


# Импорт функции определения типа дня
from src.utils import get_day_type_by_date


class WorkforceAnalyzer:
    def __init__(self, db):
        self.db = db
        # История окончания смен: { "driver_id_str": {'end_dt': datetime, 'duration': float} }
        self.history: Dict[str, Dict[str, Any]] = {}

        # Накопленные долги (отгулы): { "driver_id_str": int_days }
        self.debts: Dict[str, int] = {}

        # Накопленные часы за симуляцию (для балансировки): { "driver_id_str": float_hours }
        self.accumulated_hours: Dict[str, float] = {}

    def load_history(self, history_data: dict):
        """Загрузка истории о конце прошлого месяца)"""
        self.history = {}
        for did, data in history_data.items():
            try:
                dt_val = datetime.fromisoformat(data['end_dt']) if isinstance(data['end_dt'], str) else data['end_dt']
                self.history[str(did)] = {'end_dt': dt_val, 'duration': float(data['duration'])}
            except Exception:
                continue


    def get_history_serializable(self):
        """Выгрузка истории для JSON"""
        return {k: {'end_dt': v['end_dt'].isoformat(), 'duration': v['duration']} for k, v in self.history.items()}

    def get_debts_serializable(self):
        """Выгрузка долгов для отчета"""
        return self.debts

    def is_driver_absent(self, driver_id: int, check_date: date) -> tuple:
        """
        Проверяет по БД отсутствий (больничные, отпуска).
        Возвращает: (True/False, причина)
        """
        d_id_str = str(driver_id)
        # В self.db.absences лежат словари
        for absence in self.db.absences:
            if str(absence["driver_id"]) == d_id_str:
                # Даты в БД уже сконвертированы в date в DataLoader
                if absence["from"] <= check_date <= absence["to"]:
                    return True, absence["type"]
        return False, None

    # def generate_daily_roster(
    #         self,
    #         route_number: str,
    #         day_of_month: int,
    #         target_month: str,
    #         target_year: int,
    #         mode: str = "real"
    # ):
    #     # 1. Подготовка контекста
    #     # Локальный буфер истории, чтобы изменения вступили в силу только в конце функции
    #     daily_history_buffer = {}
    #
    #     current_day_type = get_day_type_by_date(day_of_month, target_month, year=target_year)
    #
    #     # Поиск расписания
    #     schedule = next(
    #         (s for s in self.db.schedules
    #          if str(s.route_number) == str(route_number) and s.day_type.lower() == current_day_type),
    #         None
    #     )
    #
    #     if not schedule:
    #         return {"error": f"Нет расписания ({current_day_type})"}
    #
    #     # Определение даты
    #     month_map = {
    #         "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4,
    #         "Май": 5, "Июнь": 6, "Июль": 7, "Август": 8,
    #         "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12
    #     }
    #     m_num = month_map.get(target_month)
    #     if not m_num:
    #         return {"error": f"Неизвестный месяц: {target_month}"}
    #
    #     current_date = date(target_year, m_num, day_of_month)
    #     base_dt = datetime(target_year, m_num, day_of_month)
    #
    #     # 2. Сбор и Сортировка водителей
    #     main_drivers = []
    #     reserve_drivers = []
    #
    #     # Фильтруем список
    #     for d in self.db.drivers:
    #         if d.month != target_month:
    #             continue
    #
    #         # Проверка отпусков/больничных
    #         is_absent, _ = self.is_driver_absent(d.id, current_date)
    #         if is_absent:
    #             continue
    #
    #         route = str(d.assigned_route_number).strip() if d.assigned_route_number else ""
    #
    #         # Разносим по группам
    #         if route == str(route_number):
    #             main_drivers.append(d)
    #         elif route.upper() == "ANY":
    #             reserve_drivers.append(d)
    #
    #     # СОРТИРОВКА
    #     # Ключи:
    #     # 1. Время отдыха (чем больше отдых, тем водитель лучше).
    #     # 2. Накопленные часы (чем меньше, тем водитель лучше).
    #
    #     def sort_key(driver):
    #         d_id_str = str(driver.id)
    #
    #         # Часы (для балансировки)
    #         acc_hours = self.accumulated_hours.get(d_id_str, 0.0)
    #
    #         # Отдых
    #         last_rec = self.history.get(d_id_str)
    #         if not last_rec:
    #             gap_hours = 9999.0  # Очень давно не работал, приоритет
    #         else:
    #             # Считаем разницу от "сейчас" (начала дня) до конца прошлой смены
    #             # Это грубая оценка для сортировки, точная будет внутри смены
    #             gap_hours = (base_dt - last_rec['end_dt']).total_seconds() / 3600
    #
    #         # Tuple sorting: Python сортирует по возрастанию.
    #         # Мы хотим gap_hours DESC -> берем -gap_hours
    #         # Мы хотим acc_hours ASC  -> берем acc_hours
    #         return (-gap_hours, acc_hours)
    #
    #     main_drivers.sort(key=sort_key)
    #     reserve_drivers.sort(key=sort_key)
    #
    #     # 3. Подготовка структуры ответа
    #     # Сортируем трамваи для порядка
    #     try:
    #         sorted_trams = sorted(
    #             schedule.trams,
    #             key=lambda t: int(t.number) if str(t.number).isdigit() else t.number
    #         )
    #     except Exception:
    #         sorted_trams = schedule.trams
    #
    #     tram_map = {}
    #     for tram in sorted_trams:
    #         tram_map[tram.number] = {
    #             "tram_number": tram.number,
    #             "shift_1": None,
    #             "shift_2": None,
    #             "issues": []
    #         }
    #
    #     # Вспомогательная функция обработки одной смены
    #     def process_single_shift(tram_obj, shift_data, shift_name):
    #         if not shift_data:
    #             return
    #
    #         s_start = shift_data.start
    #         s_end = shift_data.end
    #
    #         s_start_dt = self._combine_dt(base_dt, s_start)
    #         s_end_dt = self._combine_dt(base_dt, s_end)
    #
    #         # Обработка перехода через полночь
    #         if s_end_dt < s_start_dt:
    #             s_end_dt += timedelta(days=1)
    #
    #         s_dur = (s_end_dt - s_start_dt).total_seconds() / 3600
    #
    #         # --- ЭТАП 1: Поиск среди штатных и резерва ---
    #         cand, src, warns, rest_val = self._find_candidate(
    #             [main_drivers, reserve_drivers],
    #             day_of_month,
    #             shift_name,  # "1" или "2"
    #             s_start_dt,
    #             s_dur,
    #             mode,
    #             daily_buffer=daily_history_buffer  # Передаем буфер, чтобы проверить, не назначен ли уже сегодня
    #         )
    #
    #         # --- ЭТАП 2: Overtime (Работа в выходной) ---
    #         # Запускаем только если режим real, кандидата нет, и это не режим strict
    #         if not cand and mode == "real":
    #             cand, src, warns, rest_val = self._find_overtime_candidate(
    #                 self.db.drivers,  # Ищем по всей базе водителей этого месяца
    #                 day_of_month,
    #                 s_start_dt,
    #                 daily_history_buffer,
    #                 current_date,  # Для проверки отпусков
    #                 target_month
    #             )
    #
    #         # --- Запись результата ---
    #         if cand:
    #             # Формируем имя с пометками
    #             suffix = ""
    #             if src == "reserve":
    #                 suffix = " (Рез)"
    #             elif src == "overtime":
    #                 suffix = " (Вых!)"
    #
    #             result_entry = {
    #                 "driver": str(cand.id),
    #                 "driver_name": f"{cand.id}{suffix}",  # Для удобства отображения
    #                 "work_hours": round(s_dur, 2),
    #                 "rest_before": round(rest_val, 1),
    #                 "warnings": warns,
    #                 "time_range": f"{s_start}-{s_end}",
    #                 "source": src,
    #                 "debt_incurred": (src == "overtime")
    #             }
    #
    #             tram_map[tram_obj.number][f"shift_{shift_name}"] = result_entry
    #
    #             # Обновляем локальный буфер истории (чтобы этот водитель не взял вторую смену сегодня)
    #             daily_history_buffer[str(cand.id)] = {
    #                 "end_dt": s_end_dt,
    #                 "duration": s_dur
    #             }
    #
    #             # Обновляем накопленные часы в памяти (сразу, для учета в след. итерации)
    #             d_id_str = str(cand.id)
    #             self.accumulated_hours[d_id_str] = self.accumulated_hours.get(d_id_str, 0.0) + s_dur
    #
    #             # Удаляем из списков доступных (чтобы search не находил его снова для main/reserve)
    #             self._remove_driver(cand, main_drivers, reserve_drivers)
    #         else:
    #             tram_map[tram_obj.number]["issues"].append(f"Нет водителя ({shift_name})")
    #
    #
    #     # 4. Проход по сменам
    #     # Сначала все первые смены
    #     for tram in sorted_trams:
    #         process_single_shift(tram, tram.shift_1, "1")
    #
    #     # Потом все вторые смены
    #     for tram in sorted_trams:
    #         process_single_shift(tram, tram.shift_2, "2")
    #
    #
    #     # 5. Фиксация результатов
    #     # Обновляем глобальную историю
    #     self.history.update(daily_history_buffer)
    #
    #     # Обновляем долги (Debts)
    #     for t_data in tram_map.values():
    #         for s in ['shift_1', 'shift_2']:
    #             if t_data[s] and t_data[s].get('debt_incurred'):
    #                 drv_id = t_data[s]['driver']
    #                 self.debts[drv_id] = self.debts.get(drv_id, 0) + 1
    #
    #     roster = list(tram_map.values())
    #     return {
    #         "date": day_of_month,
    #         "route": route_number,
    #         "roster": roster
    #     }


    def generate_daily_roster(
            self,
            route_number: str,
            day_of_month: int,
            target_month: str,
            target_year: int,
            mode: str = "real"
    ):
        """
        Новая версия метода - использует централизованную логику для избежания конфликтов водителей ANY.
        Обеспечивает обратную совместимость с существующим API.
        """
        results = self.generate_daily_roster_for_all_routes(
            [route_number], day_of_month, target_month, target_year, mode
        )
        return results[route_number]


    def generate_daily_roster_for_all_routes(
            self,
            routes_list: List[str],
            day_of_month: int,
            target_month: str,
            target_year: int,
            mode: str = "real"
    ):
        """
        Генерирует расписание для всех маршрутов одновременно с учетом межмаршрутных конфликтов.
        Решает проблему с водителями ANY, которые могут назначаться на несколько маршрутов в один день.
        """
        # Единый буфер истории для всех маршрутов в этот день
        daily_history_buffer = {}
        results_by_route = {}

        # Сортируем маршруты в порядке приоритета: 9, 20, 21, 47, 48, 55, 61
        priority_order = ["9", "20", "21", "47", "48", "55", "61"]
        sorted_routes = sorted(routes_list, key=lambda x: priority_order.index(x) if x in priority_order else 999)

        # Обрабатываем каждый маршрут по очереди
        for route in sorted_routes:
            result = self._generate_single_route_roster(
                route, day_of_month, target_month, target_year, mode, daily_history_buffer
            )
            results_by_route[route] = result

        # Обновляем глобальную историю один раз в конце дня
        self.history.update(daily_history_buffer)

        return results_by_route

    def _generate_single_route_roster(
            self,
            route_number: str,
            day_of_month: int,
            target_month: str,
            target_year: int,
            mode: str,
            daily_history_buffer: Dict[str, Dict[str, Any]]
    ):
        """
        Генерирует расписание для одного маршрута с учетом уже назначенных водителей в daily_history_buffer.
        Это внутренний метод, который используется в generate_daily_roster_for_all_routes.
        """
        # 1. Подготовка контекста (аналогично оригинальному методу)
        current_day_type = get_day_type_by_date(day_of_month, target_month, year=target_year)

        # Поиск расписания
        schedule = next(
            (s for s in self.db.schedules
             if str(s.route_number) == str(route_number) and s.day_type.lower() == current_day_type),
            None
        )

        if not schedule:
            return {"error": f"Нет расписания ({current_day_type})"}

        # Определение даты
        month_map = {
            "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4,
            "Май": 5, "Июнь": 6, "Июль": 7, "Август": 8,
            "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12
        }
        m_num = month_map.get(target_month)
        if not m_num:
            return {"error": f"Неизвестный месяц: {target_month}"}

        current_date = date(target_year, m_num, day_of_month)
        base_dt = datetime(target_year, m_num, day_of_month)

        # 2. Сбор и Сортировка водителей
        main_drivers = []
        reserve_drivers = []

        # Фильтруем список
        for d in self.db.drivers:
            if d.month != target_month:
                continue

            # Проверка отпусков/больничных
            is_absent, _ = self.is_driver_absent(d.id, current_date)
            if is_absent:
                continue

            route = str(d.assigned_route_number).strip() if d.assigned_route_number else ""

            # Разносим по группам
            if route == str(route_number):
                main_drivers.append(d)
            elif route.upper() == "ANY":
                reserve_drivers.append(d)

        # СОРТИРОВКА (аналогично оригинальному методу)
        def sort_key(driver):
            d_id_str = str(driver.id)

            # Часы (для балансировки)
            acc_hours = self.accumulated_hours.get(d_id_str, 0.0)

            # Отдых
            last_rec = self.history.get(d_id_str)
            if not last_rec:
                gap_hours = 9999.0  # Очень давно не работал, приоритет
            else:
                gap_hours = (base_dt - last_rec['end_dt']).total_seconds() / 3600

            return (-gap_hours, acc_hours)

        main_drivers.sort(key=sort_key)
        reserve_drivers.sort(key=sort_key)

        # 3. Подготовка структуры ответа
        try:
            sorted_trams = sorted(
                schedule.trams,
                key=lambda t: int(t.number) if str(t.number).isdigit() else t.number
            )
        except Exception:
            sorted_trams = schedule.trams

        tram_map = {}
        for tram in sorted_trams:
            tram_map[tram.number] = {
                "tram_number": tram.number,
                "shift_1": None,
                "shift_2": None,
                "issues": []
            }

        # Вспомогательная функция обработки одной смены
        def process_single_shift(tram_obj, shift_data, shift_name):
            if not shift_data:
                return

            s_start = shift_data.start
            s_end = shift_data.end

            s_start_dt = self._combine_dt(base_dt, s_start)
            s_end_dt = self._combine_dt(base_dt, s_end)

            # Обработка перехода через полночь
            if s_end_dt < s_start_dt:
                s_end_dt += timedelta(days=1)

            s_dur = (s_end_dt - s_start_dt).total_seconds() / 3600

            # --- ЭТАП 1: Поиск среди штатных и резерва ---
            cand, src, warns, rest_val = self._find_candidate(
                [main_drivers, reserve_drivers],
                day_of_month,
                shift_name,  # "1" или "2"
                s_start_dt,
                s_dur,
                mode,
                daily_buffer=daily_history_buffer  # ВАЖНО: используем общий буфер
            )

            # --- ЭТАП 2: Overtime (Работа в выходной) ---
            if not cand and mode == "real":
                cand, src, warns, rest_val = self._find_overtime_candidate(
                    self.db.drivers,
                    day_of_month,
                    s_start_dt,
                    daily_history_buffer,  # ВАЖНО: используем общий буфер
                    current_date,
                    target_month
                )

            # --- Запись результата ---
            if cand:
                # Формируем имя с пометками
                suffix = ""
                if src == "reserve":
                    suffix = " (Рез)"
                elif src == "overtime":
                    suffix = " (Вых!)"

                result_entry = {
                    "driver": str(cand.id),
                    "driver_name": f"{cand.id}{suffix}",
                    "work_hours": round(s_dur, 2),
                    "rest_before": round(rest_val, 1),
                    "warnings": warns,
                    "time_range": f"{s_start}-{s_end}",
                    "source": src,
                    "debt_incurred": (src == "overtime")
                }

                tram_map[tram_obj.number][f"shift_{shift_name}"] = result_entry

                # Обновляем общий буфер истории
                daily_history_buffer[str(cand.id)] = {
                    "end_dt": s_end_dt,
                    "duration": s_dur
                }

                # Обновляем накопленные часы
                d_id_str = str(cand.id)
                self.accumulated_hours[d_id_str] = self.accumulated_hours.get(d_id_str, 0.0) + s_dur

                # Удаляем из списков доступных
                self._remove_driver(cand, main_drivers, reserve_drivers)
            else:
                tram_map[tram_obj.number]["issues"].append(f"Нет водителя ({shift_name})")

        # 4. Проход по сменам
        for tram in sorted_trams:
            process_single_shift(tram, tram.shift_1, "1")

        for tram in sorted_trams:
            process_single_shift(tram, tram.shift_2, "2")

        # 5. Обновляем долги (НЕ обновляем глобальную историю здесь - это делается в родительском методе)
        for t_data in tram_map.values():
            for s in ['shift_1', 'shift_2']:
                if t_data[s] and t_data[s].get('debt_incurred'):
                    drv_id = t_data[s]['driver']
                    self.debts[drv_id] = self.debts.get(drv_id, 0) + 1

        roster = list(tram_map.values())
        return {
            "date": day_of_month,
            "route": route_number,
            "roster": roster
        }

    def load_history_for_all_routes(self, routes_list: List[str], prev_month_name: str, prev_year: int):
        """
        Загружает историю всех маршрутов в единый объект для корректного учета межмаршрутных конфликтов.
        """
        from src.utils import get_month_number
        import os
        import json
        from src.config import HISTORY_DIR

        combined_history = {}

        for route in routes_list:
            try:
                prev_month_num = get_month_number(prev_month_name)
                prev_folder = f"{prev_month_num:02d}_{prev_month_name}_{prev_year}"
                prev_file = f"history_{route}_{prev_month_name}_{prev_year}.json"
                prev_hist_path = os.path.join(HISTORY_DIR, prev_folder, prev_file)

                if os.path.exists(prev_hist_path):
                    with open(prev_hist_path, "r", encoding="utf-8") as f:
                        route_history = json.load(f)
                        combined_history.update(route_history)
            except Exception as e:
                # Логируем ошибку, но продолжаем работу
                print(f"Ошибка загрузки истории маршрута {route}: {e}")
                continue

        # Загружаем объединенную историю
        self.load_history(combined_history)
        return len(combined_history)

    # ==========================================================
    # ВНУТРЕННЯЯ ЛОГИКА ПОИСКА
    # ==========================================================

    def _find_candidate(self, groups, day, target_shift, shift_start, shift_dur, mode, daily_buffer):
        """Стандартный поиск по спискам Main и Reserve"""
        group_names = ["main", "reserve"]

        for i, drivers in enumerate(groups):
            source = group_names[i]
            for driver in drivers:
                # 1. Проверка: уже работал сегодня? (Смотрим буфер)
                if str(driver.id) in daily_buffer:
                    continue

                # 2. Проверка статуса (Строгое соответствие: 1 или 2)
                status = driver.get_status_for_day(day)
                if status != target_shift:
                    continue

                # 3. Проверка отдыха
                warnings, rest_fact = self._check_rest(driver.id, shift_start)

                # Если strict mode и есть нарушения - пропускаем
                if warnings and mode == "strict":
                    continue

                # Нашли
                return driver, source, warnings, rest_fact

        return None, None, [], 0

    def _find_overtime_candidate(self, all_drivers, day, shift_start, daily_buffer, current_date, target_month):
        """Поиск водителя, у которого выходной (Overtime)"""

        candidates = []

        for driver in all_drivers:
            # Только текущий месяц
            if driver.month != target_month: continue

            d_id = str(driver.id)

            # Не должен быть занят сегодня
            if d_id in daily_buffer: continue

            # Не должен быть в отпуске/больничном
            is_absent, _ = self.is_driver_absent(driver.id, current_date)
            if is_absent: continue

            # ИСКЛЮЧАЕМ водителей ANY - они должны соблюдать свой график!
            # Водители ANY работают только согласно своему табелю, не в выходные
            route = str(driver.assigned_route_number).strip() if driver.assigned_route_number else ""
            if route.upper() == "ANY":
                continue

            # Статус должен быть "В"
            # Если у вас есть другие обозначения выходных, добавьте их в список
            st = driver.get_status_for_day(day)
            if st not in ["В"]:
                continue

            # Проверка отдыха (Даже в выходной нельзя выводить, если мало отдыхал)
            warnings, rest_fact = self._check_rest(d_id, shift_start)
            if warnings:
                continue  # С переработками берем только тех, кто реально отдохнул

            # Получаем часы для сортировки
            acc = self.accumulated_hours.get(d_id, 0.0)
            candidates.append((driver, rest_fact, acc))

        # Сортируем кандидатов Overtime
        # Приоритет 1: Самый отдохнувший (rest_fact DESC)
        # Приоритет 2: Меньше всего часов (acc ASC)
        if candidates:
            candidates.sort(key=lambda x: (-x[1], x[2]))
            best = candidates[0]
            return best[0], "overtime", ["Работа в выходной"], best[1]

        return None, None, [], 0

    def _check_rest(self, driver_id, current_start_dt):
        """Проверка межсменного отдыха с учетом нормы 12ч или 2*duration"""
        last_rec = self.history.get(str(driver_id))

        # Если истории нет - считаем, что отдыхал бесконечно
        if not last_rec:
            return [], 999.0

        last_end = last_rec['end_dt']
        last_dur = last_rec['duration']

        gap_hours = (current_start_dt - last_end).total_seconds() / 3600

        if gap_hours < 0:
            return ["Накладка смен"], gap_hours

        # Норматив
        required = max(12, 2 * last_dur)

        # Правило 42 часов (еженедельный отдых).
        if gap_hours > 24:
            required += 42

        warns = []
        if gap_hours < required:
            warns.append(f"Недоотдых ({round(gap_hours, 1)}ч < {round(required, 1)}ч)")

        return warns, gap_hours

    def _combine_dt(self, base_date, time_str):
        try:
            h, m = map(int, time_str.split(':'))
            return base_date + timedelta(hours=h, minutes=m)
        except:
            return base_date

    def _remove_driver(self, cand, main, reserve):
        # Удаляем из списков по id, так как объекты могут быть разными копиями (в теории)
        # Но так как мы работаем с одной сущностью DataLoader, достаточно remove по объекту
        if cand in main:
            main.remove(cand)
        elif cand in reserve:
            reserve.remove(cand)