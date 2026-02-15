from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple, Any

# Импорт функции определения типа дня
from src.utils import get_day_type_by_date
from src.logger import get_logger

logger = get_logger(__name__)


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
        """Загрузка истории о конце прошлого месяца"""
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
        for absence in self.db.absences:
            if str(absence["driver_id"]) == d_id_str:
                if absence["from"] <= check_date <= absence["to"]:
                    return True, absence["type"]
        return False, None

    def generate_daily_roster(
            self,
            route_number: str,
            day_of_month: int,
            target_month: str,
            target_year: int,
            mode: str = "real"
    ):
        """
        Обертка для обратной совместимости.
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
        Генерирует расписание для всех маршрутов одновременно.
        """
        # Единый буфер истории для всех маршрутов в этот день
        daily_history_buffer = {}
        results_by_route = {}

        # Сортируем маршруты в порядке приоритета
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
        Генерирует расписание для одного маршрута в режиме 'ЕДИНОГО ПАРКА'.
        Игнорирует закрепление за маршрутом ради минимизации штата (приоритет ID).
        """
        # 1. Подготовка контекста
        current_day_type = get_day_type_by_date(day_of_month, target_month, year=target_year)

        schedule = next(
            (s for s in self.db.schedules
             if str(s.route_number) == str(route_number) and s.day_type.lower() == current_day_type),
            None
        )

        if not schedule:
            return {"error": f"Нет расписания ({current_day_type})"}

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

        # 2. Сбор ВСЕХ водителей в одну кучу (без разделения на Main/Reserve)
        all_candidates = []

        for d in self.db.drivers:
            if d.month != target_month:
                continue

            # Проверка отпусков/больничных
            is_absent, _ = self.is_driver_absent(d.id, current_date)
            if is_absent:
                continue

            # Проверка: уже работал сегодня?
            if str(d.id) in daily_history_buffer:
                continue

            # В режиме синтетики берем всех
            all_candidates.append(d)

        # --- СОРТИРОВКА: АБСОЛЮТНАЯ ВЛАСТЬ ID ---
        # Цель: всегда брать водителей 1, 2, 3... пока они свободны.
        def universal_sort_key(driver):
            d_id_str = str(driver.id)

            # 1. Приоритет: Тот, кто УЖЕ начал работать в этом месяце.
            # Это не дает штату "расползаться" в середине месяца.
            acc_hours = self.accumulated_hours.get(d_id_str, 0.0)
            has_hours = 1 if acc_hours > 0 else 0

            # 2. Приоритет: Наименьший ID
            try:
                id_val = int(d_id_str)
            except ValueError:
                id_val = 999999

            # 3. Приоритет: Время отдыха (чтобы не брать уставших)
            last_rec = self.history.get(d_id_str)
            if not last_rec:
                gap_hours = 9999.0
            else:
                gap_hours = (base_dt - last_rec['end_dt']).total_seconds() / 3600

            # Сортировка (Python sort is stable ASC):
            # -has_hours (1 -> -1 (first), 0 -> 0 (last))
            # id_val (ASC)
            # -gap_hours (DESC)
            return (-has_hours, id_val, -gap_hours)

        all_candidates.sort(key=universal_sort_key)

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
            if s_end_dt < s_start_dt:
                s_end_dt += timedelta(days=1)
            s_dur = (s_end_dt - s_start_dt).total_seconds() / 3600

            # --- ЭТАП 1: Поиск в ЕДИНОМ списке ---
            # Передаем одну общую группу. Источник будет называться "main" (т.к. индекс 0)
            # Но для нас это неважно, главное - эффективность.
            cand, src, warns, rest_val = self._find_candidate(
                [all_candidates],
                day_of_month,
                shift_name,
                s_start_dt,
                s_dur,
                mode,
                daily_buffer=daily_history_buffer
            )

            # --- ЭТАП 2: Overtime (Работа в выходной) ---
            if not cand and mode == "real":
                cand, src, warns, rest_val = self._find_overtime_candidate(
                    self.db.drivers,
                    day_of_month,
                    s_start_dt,
                    daily_history_buffer,
                    current_date,
                    target_month
                )

            # --- Запись результата ---
            if cand:
                # Красивое имя источника, если нужно
                # Так как src="main" (из индекса), можем переименовать в "pool"
                display_src = "pool" if src == "main" else src

                suffix = ""
                if display_src == "overtime": suffix = " (Вых!)"

                result_entry = {
                    "driver": str(cand.id),
                    "driver_name": f"{cand.id}{suffix}",
                    "work_hours": round(s_dur, 2),
                    "rest_before": round(rest_val, 1),
                    "warnings": warns,
                    "time_range": f"{s_start}-{s_end}",
                    "source": display_src,
                    "debt_incurred": (src == "overtime")
                }

                tram_map[tram_obj.number][f"shift_{shift_name}"] = result_entry

                # Обновляем буферы
                daily_history_buffer[str(cand.id)] = {"end_dt": s_end_dt, "duration": s_dur}
                d_id_str = str(cand.id)
                self.accumulated_hours[d_id_str] = self.accumulated_hours.get(d_id_str, 0.0) + s_dur

                # Удаляем из списка кандидатов (он один)
                if cand in all_candidates:
                    all_candidates.remove(cand)
            else:
                tram_map[tram_obj.number]["issues"].append(f"Нет водителя ({shift_name})")

        # 4. Проход по сменам
        for tram in sorted_trams: process_single_shift(tram, tram.shift_1, "1")
        for tram in sorted_trams: process_single_shift(tram, tram.shift_2, "2")

        # 5. Обновляем долги
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
                        combined_history.update(json.load(f))
            except Exception:
                continue

        self.load_history(combined_history)
        return len(combined_history)

    # ==========================================================
    # ВНУТРЕННЯЯ ЛОГИКА ПОИСКА
    # ==========================================================

    def _find_candidate(self, groups, day, target_shift, shift_start, shift_dur, mode, daily_buffer):
        """
        Ищет кандидата в списках: Main, Reserve, Borrowed
        """
        # Исправленный список имен
        group_names = ["main", "reserve", "borrowed"]

        for i, drivers in enumerate(groups):
            # Безопасное получение имени источника
            source = group_names[i] if i < len(group_names) else "unknown"

            for driver in drivers:
                if str(driver.id) in daily_buffer: continue

                status = driver.get_status_for_day(day)
                if status != target_shift: continue

                warnings, rest_fact = self._check_rest(driver.id, shift_start)
                if warnings and mode == "strict": continue

                return driver, source, warnings, rest_fact

        return None, None, [], 0

    def _find_overtime_candidate(self, all_drivers, day, shift_start, daily_buffer, current_date, target_month):
        """Поиск водителя для Overtime (выходной)"""
        candidates = []
        for driver in all_drivers:
            if driver.month != target_month: continue
            d_id = str(driver.id)
            if d_id in daily_buffer: continue

            is_absent, _ = self.is_driver_absent(driver.id, current_date)
            if is_absent: continue

            route = str(driver.assigned_route_number).strip() if driver.assigned_route_number else ""
            if route.upper() == "ANY": continue

            st = driver.get_status_for_day(day)
            if st not in ["В"]: continue

            warnings, rest_fact = self._check_rest(d_id, shift_start)
            if warnings: continue

            acc = self.accumulated_hours.get(d_id, 0.0)
            candidates.append((driver, rest_fact, acc))

        if candidates:
            # Сортировка Overtime: кто лучше отдохнул и у кого меньше часов
            candidates.sort(key=lambda x: (-x[1], x[2]))
            best = candidates[0]
            return best[0], "overtime", ["Работа в выходной"], best[1]

        return None, None, [], 0

    def _check_rest(self, driver_id, current_start_dt):
        last_rec = self.history.get(str(driver_id))
        if not last_rec: return [], 999.0

        last_end = last_rec['end_dt']
        last_dur = last_rec['duration']
        gap_hours = (current_start_dt - last_end).total_seconds() / 3600

        if gap_hours < 0: return ["Накладка смен"], gap_hours

        required = max(12, 2 * last_dur)
        if gap_hours > 24: required += 42

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
        if cand in main:
            main.remove(cand)
        elif cand in reserve:
            reserve.remove(cand)