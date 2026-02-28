import json
import os
from datetime import datetime, timedelta, date
from typing import List, Dict, Any

from src.utils import get_day_type_by_date


class WorkforceAnalyzer:
    def __init__(self, db):
        self.db = db
        # История окончания смен
        self.history: Dict[str, Dict[str, Any]] = {}
        # Накопленные часы
        self.accumulated_hours: Dict[str, float] = {}

        # Нормы часов
        self.norms = {}
        self._load_norms()

    def _load_norms(self):
        possible_paths = [
            "env_synthetic/data/norms_2026.json",
            "data/norms_2026.json",
            "norms_2026.json"
        ]
        loaded = False
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self.norms = json.load(f)
                    loaded = True
                    break
                except Exception as e:
                    print(f"Ошибка чтения норм из {path}: {e}")

        if not loaded:
            pass

    def _get_driver_norm(self, driver_obj, year, month_name):
        year_str = str(year)
        if year_str not in self.norms or month_name not in self.norms[year_str]:
            return 160.0

        month_norms = self.norms[year_str][month_name]
        sch = "?"
        if hasattr(driver_obj, 'schedule_pattern'):
            sch = str(driver_obj.schedule_pattern)
        elif hasattr(driver_obj, 'schedule'):
            sch = str(driver_obj.schedule)

        if "4" in sch and "2" in sch:
            return month_norms.get("33h", 150.0)
        else:
            return month_norms.get("40h", 168.0)

    def load_history(self, history_data: dict):
        self.history = {}
        for did, data in history_data.items():
            try:
                dt_val = datetime.fromisoformat(data['end_dt']) if isinstance(data['end_dt'], str) else data['end_dt']
                self.history[str(did)] = {
                    'end_dt': dt_val,
                    'duration': float(data['duration'])
                }
            except Exception:
                continue

    def get_history_serializable(self):
        return {
            k: {'end_dt': v['end_dt'].isoformat(), 'duration': v['duration']}
            for k, v in self.history.items()
        }

    def is_driver_absent(self, driver_id: int, check_date: date) -> tuple:
        d_id_str = str(driver_id)
        for absence in self.db.absences:
            if str(absence["driver_id"]) == d_id_str:
                if absence["from"] <= check_date <= absence["to"]:
                    return True, absence["type"]
        return False, None

    def generate_daily_roster_for_all_routes(self, routes_list: List[str], day_of_month: int, target_month: str,
                                             target_year: int, mode: str = "real"):
        daily_history_buffer = {}
        results_by_route = {}

        priority_order = ["9", "20", "21", "47", "48", "55", "61"]
        sorted_routes = sorted(routes_list, key=lambda x: priority_order.index(x) if x in priority_order else 999)

        for route in sorted_routes:
            result = self._generate_single_route_roster(route, day_of_month, target_month, target_year, mode,
                                                        daily_history_buffer)
            results_by_route[route] = result

        self.history.update(daily_history_buffer)
        return results_by_route

    def _generate_single_route_roster(self, route_number: str, day_of_month: int, target_month: str, target_year: int,
                                      mode: str, daily_history_buffer: Dict[str, Dict[str, Any]]):
        current_day_type = get_day_type_by_date(day_of_month, target_month, year=target_year)

        schedule = next((s for s in self.db.schedules if
                         str(s.route_number) == str(route_number) and s.day_type.lower() == current_day_type), None)

        if not schedule:
            return {"date": day_of_month, "route": route_number, "roster": [], "driver_stat_flags": {},
                    "error": "Нет расписания"}

        month_map = {"Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6,
                     "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12}
        m_num = month_map.get(target_month, 1)
        current_date = date(target_year, m_num, day_of_month)
        base_dt = datetime(target_year, m_num, day_of_month)

        assigned_drivers = []
        free_drivers = []

        for d in self.db.drivers:
            if d.month != target_month: continue
            is_absent, _ = self.is_driver_absent(d.id, current_date)
            if is_absent: continue

            r_num = str(d.assigned_route_number) if d.assigned_route_number else None

            if r_num == str(route_number):
                assigned_drivers.append(d)
            elif r_num in [None, "", "None", "0", "ANY"]:
                free_drivers.append(d)

        # ЖАДНАЯ СОРТИРОВКА (GREEDY)
        def greedy_sort_key(d):
            d_id = str(d.id)
            hours = self.accumulated_hours.get(d_id, 0.0)
            try:
                id_val = int(d_id)
            except:
                id_val = 999999
            return (-hours, id_val)

        assigned_drivers.sort(key=greedy_sort_key)
        free_drivers.sort(key=greedy_sort_key)

        trams_list = schedule.trams if isinstance(schedule.trams, list) else []

        def tram_sort_key(t):
            val = str(t.number)
            if val.isdigit(): return (0, int(val))
            return (1, val)

        sorted_trams = sorted(trams_list, key=tram_sort_key)

        tram_map = {}
        earliest_start_dt = base_dt + timedelta(hours=23, minutes=59)

        for tram in sorted_trams:
            tram_map[tram.number] = {"tram_number": tram.number, "shift_1": None, "shift_2": None, "issues": []}
            if tram.shift_1:
                start_dt = self._combine_dt(base_dt, tram.shift_1.start)
                if start_dt < earliest_start_dt: earliest_start_dt = start_dt

        if earliest_start_dt > base_dt + timedelta(hours=20):
            earliest_start_dt = base_dt + timedelta(hours=5)

        worked_drivers_ids = set()

        def process_single_shift(tram_obj, shift_data, shift_name):
            if not shift_data: return
            s_start_dt = self._combine_dt(base_dt, shift_data.start)
            s_end_dt = self._combine_dt(base_dt, shift_data.end)
            if s_end_dt < s_start_dt: s_end_dt += timedelta(days=1)

            s_dur = (s_end_dt - s_start_dt).total_seconds() / 3600

            cand, src, warns, rest_val = self._find_candidate(
                [assigned_drivers], day_of_month, shift_name, s_start_dt, s_dur, mode,
                daily_history_buffer, target_year, target_month
            )

            if not cand:
                cand, src, warns, rest_val = self._find_candidate(
                    [free_drivers], day_of_month, shift_name, s_start_dt, s_dur, mode,
                    daily_history_buffer, target_year, target_month
                )
                if cand: src = "recruit"

            if not cand and mode == "real":
                cand, src, warns, rest_val = self._find_overtime_candidate(
                    [assigned_drivers, free_drivers], day_of_month, shift_name, s_start_dt, s_dur,
                    daily_history_buffer, target_year, target_month
                )

            if cand:
                tram_map[tram_obj.number][f"shift_{shift_name}"] = {
                    "driver": str(cand.id),
                    "driver_name": f"{cand.id}",
                    "work_hours": round(s_dur, 2),
                    "rest_before": round(rest_val, 1),
                    "warnings": warns,  # Сюда попадает "(!)" если отдых неидеальный
                    "time_range": f"{shift_data.start}-{shift_data.end}",
                    "source": src
                }

                daily_history_buffer[str(cand.id)] = {"end_dt": s_end_dt, "duration": s_dur}
                worked_drivers_ids.add(str(cand.id))
                self.accumulated_hours[str(cand.id)] = self.accumulated_hours.get(str(cand.id), 0.0) + s_dur
            else:
                tram_map[tram_obj.number]["issues"].append(f"Нет водителя ({shift_name})")

        for tram in sorted_trams: process_single_shift(tram, tram.shift_1, "1")
        for tram in sorted_trams: process_single_shift(tram, tram.shift_2, "2")

        # --- ЗАПОЛНЕНИЕ СТАТУСОВ ДЛЯ ОТЧЕТА ---
        driver_stat_flags = {}
        for drv in assigned_drivers:
            d_id = str(drv.id)
            if d_id in worked_drivers_ids: continue

            plan = drv.get_status_for_day(day_of_month)

            if plan in ["1", "2"]:
                norm = self._get_driver_norm(drv, target_year, target_month)
                curr_hours = self.accumulated_hours.get(d_id, 0.0)

                # В Real режиме проверяем с учетом допуска
                limit = norm
                if mode == "real": limit += 30.0

                if curr_hours + 8.0 > limit:
                    driver_stat_flags[d_id] = "norm_limit"
                else:
                    # В статусах (Красный) показываем только БЛОКИРУЮЩИЕ проблемы
                    warns, _ = self._check_rest(drv, earliest_start_dt, mode=mode)
                    if warns:
                        driver_stat_flags[d_id] = "low_rest"
                    else:
                        driver_stat_flags[d_id] = "reserve"

        return {
            "date": day_of_month,
            "route": route_number,
            "roster": list(tram_map.values()),
            "driver_stat_flags": driver_stat_flags
        }

    def _find_candidate(self, groups, day, target_shift, shift_start, shift_dur, mode, daily_buffer, year, month):
        group_names = ["main", "reserve"]
        for i, drivers in enumerate(groups):
            source = group_names[i]
            for driver in drivers:
                d_id = str(driver.id)
                if d_id in daily_buffer: continue

                status = driver.get_status_for_day(day)
                if status != target_shift: continue

                # ПРОВЕРКА НОРМЫ
                norm = self._get_driver_norm(driver, year, month)
                curr_hours = self.accumulated_hours.get(d_id, 0.0)

                # В Real режиме разрешаем переработку до 30 часов
                limit = norm
                if mode == "real": limit += 30.0

                if curr_hours + shift_dur > limit: continue

                # ПРОВЕРКА ОТДЫХА (Блокирующая)
                warnings, rest_fact = self._check_rest(driver, shift_start, mode=mode)
                if warnings: continue  # Если вернулся список - значит это запрет

                # ПРОВЕРКА ПРЕДУПРЕЖДЕНИЙ (Мягкая)
                # Если режим Real, и отдых меньше идеального (2 * работа), но больше 12 -> добавляем "(!)"
                soft_warns = []
                if mode == "real":
                    last_rec = self.history.get(d_id)
                    if last_rec:
                        ideal_rest = 2 * last_rec['duration']
                        if rest_fact < ideal_rest and rest_fact < 72:  # 72 - это "свежий"
                            soft_warns.append("(!)")

                return driver, source, soft_warns, rest_fact
        return None, None, [], 0

    def _find_overtime_candidate(self, groups, day, target_shift, shift_start, shift_dur, daily_buffer, year, month):
        """Ищет кандидата для выхода в выходной (Только Real)"""
        for drivers in groups:
            for driver in drivers:
                d_id = str(driver.id)
                if d_id in daily_buffer: continue

                status = driver.get_status_for_day(day)
                if status in ["1", "2"]: continue  # Должен был работать, но не прошел фильтр выше

                norm = self._get_driver_norm(driver, year, month)
                curr_hours = self.accumulated_hours.get(d_id, 0.0)
                if curr_hours + shift_dur > (norm + 40.0): continue  # Для овертайма лимит еще мягче

                warnings, rest_fact = self._check_rest(driver, shift_start, mode="real")
                if warnings: continue

                soft_warns = ["Работа в выходной"]
                # Тоже проверяем "неидеальный" отдых
                last_rec = self.history.get(d_id)
                if last_rec:
                    ideal_rest = 2 * last_rec['duration']
                    if rest_fact < ideal_rest and rest_fact < 72:
                        soft_warns.append("(!)")

                return driver, "overtime", soft_warns, rest_fact

        return None, None, [], 0

    def _check_rest(self, driver_obj, current_start_dt, mode="real"):
        """
        Проверка БЛОКИРУЮЩЕГО отдыха.
        Возвращает ошибку ТОЛЬКО если работать НЕЛЬЗЯ.
        """
        d_id = str(driver_obj.id)
        last_rec = self.history.get(d_id)

        if not last_rec: return [], 999.0

        last_end = last_rec['end_dt']
        last_dur = last_rec['duration']
        gap_hours = (current_start_dt - last_end).total_seconds() / 3600

        if gap_hours < 0: return ["Накладка смен"], gap_hours
        if gap_hours > 72: return [], gap_hours

        warns = []

        if mode == "strict":
            # В строгом режиме: Меньше 2*работа -> БЛОК
            required = 2 * last_dur
            if required < 12: required = 12
            if gap_hours < required:
                warns.append(f"Мало отдыха (Strict): {gap_hours:.1f} < {required:.1f}")
        else:
            # В реальном режиме: Меньше 12 -> БЛОК
            # А если между 12 и 2*работа -> ЭТО НЕ БЛОК (предупреждение добавится в _find_candidate)
            required_min = 12.0
            if gap_hours < required_min:
                warns.append(f"Критически мало отдыха: {gap_hours:.1f} < 12")

        return warns, gap_hours

    def _combine_dt(self, base_date, time_str):
        try:
            h, m = map(int, time_str.split(':'))
            return base_date + timedelta(hours=h, minutes=m)
        except:
            return base_date