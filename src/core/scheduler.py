import json
import os
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Tuple
from src.utils import get_day_type_by_date
import src.config as config  # <--- Импортируем конфиг


class WorkforceAnalyzer:
    def __init__(self, db):
        self.db = db
        self.history: Dict[str, Dict[str, Any]] = {}
        self.accumulated_hours: Dict[str, float] = {}
        self.norms = {}
        self._load_norms()

    def _load_norms(self):
        possible_paths = [
            "env_synthetic/data/norms_2026.json",
            "data/norms_2026.json",
            "norms_2026.json"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self.norms = json.load(f)
                    return
                except Exception:
                    pass

    def _get_driver_norm(self, driver_obj, year, month_name):
        year_str = str(year)
        if year_str not in self.norms or month_name not in self.norms[year_str]:
            return 160.0

        month_norms = self.norms[year_str][month_name]
        raw_pattern = str(getattr(driver_obj, "schedule_pattern", getattr(driver_obj, "schedule", ""))).lower()
        pattern = raw_pattern.replace('х', 'x')

        if "5x2" in pattern: return month_norms.get("40h", 160.0)
        if "4x2" in pattern: return month_norms.get("33h", 150.0)
        return 160.0

    def load_history_for_all_routes(self, routes, month, year):
        return 0

    def get_history_serializable(self):
        return {
            k: {'end_dt': v['end_dt'].isoformat() if isinstance(v['end_dt'], datetime) else v['end_dt'],
                'duration': v['duration']}
            for k, v in self.history.items()
        }

    def is_driver_absent(self, driver_id: str, check_date: date) -> Tuple[bool, str]:
        d_id_str = str(driver_id)
        for absence in self.db.absences:
            if isinstance(absence, dict):
                a_id = str(absence.get("driver_id"))
                start = absence.get("from") or absence.get("start_date")
                end = absence.get("to") or absence.get("end_date")
                reason = absence.get("type", "absence")
            else:
                a_id = str(getattr(absence, "driver_id", ""))
                start = getattr(absence, "start_date", getattr(absence, "from_date", None))
                end = getattr(absence, "end_date", getattr(absence, "to_date", None))
                reason = getattr(absence, "type", "absence")

            if a_id == d_id_str and start and end:
                if isinstance(start, str):
                    try:
                        start = datetime.strptime(start, "%Y-%m-%d").date()
                    except:
                        pass
                if isinstance(end, str):
                    try:
                        end = datetime.strptime(end, "%Y-%m-%d").date()
                    except:
                        pass
                if start <= check_date <= end:
                    return True, reason
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
                                      mode: str, daily_history_buffer: Dict[str, Any]):
        current_day_type = get_day_type_by_date(day_of_month, target_month, year=target_year)
        month_map = {"Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6, "Июль": 7, "Август": 8,
                     "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12}
        m_num = month_map.get(target_month, 1)
        current_date = date(target_year, m_num, day_of_month)
        base_dt = datetime(target_year, m_num, day_of_month)
        is_weekend = current_date.weekday() >= 5

        schedule = next((s for s in self.db.schedules if
                         str(s.route_number) == str(route_number) and s.day_type.lower() == current_day_type), None)
        if not schedule:
            return {"date": day_of_month, "route": route_number, "roster": [], "driver_stat_flags": {},
                    "error": "Нет расписания"}

        # 1. Сбор водителей
        assigned_drivers = []
        free_drivers = []
        for d in self.db.drivers:
            if hasattr(d, 'month') and d.month != target_month: continue
            is_absent, _ = self.is_driver_absent(d.id, current_date)
            if is_absent: continue

            r_num = str(d.assigned_route_number) if d.assigned_route_number else None
            if r_num == str(route_number):
                assigned_drivers.append(d)
            elif r_num in [None, "", "None", "0", "ANY"]:
                free_drivers.append(d)

        # 2. Сортировка с использованием КОНФИГА
        def smart_sort_key(driver):
            d_id = str(driver.id)
            hours_worked = self.accumulated_hours.get(d_id, 0.0)
            norm = self._get_driver_norm(driver, target_year, target_month)

            raw_pattern = str(getattr(driver, "schedule_pattern", getattr(driver, "schedule", ""))).lower()
            pattern = raw_pattern.replace('х', 'x')
            is_5x2 = "5x2" in pattern

            weight = 0.0

            # Лимиты берем из конфига
            soft_limit = norm + config.OVERTIME_SOFT_LIMIT

            if hours_worked > 0:
                # ВОДИТЕЛЬ В ШТАТЕ
                if hours_worked < norm:
                    # УРОВЕНЬ 1: "Голодные"
                    weight -= 10_000_000.0
                    weight -= hours_worked

                elif hours_worked < soft_limit:
                    # УРОВЕНЬ 2: "Мягкий потолок"
                    weight -= 5_000_000.0
                    weight += hours_worked

                else:
                    # УРОВЕНЬ 4: "Выгоревшие" (Выше Soft Limit)
                    weight += 10_000_000.0
                    weight += hours_worked
            else:
                # УРОВЕНЬ 3: "Новички"
                pass

            # Бонус графика 5x2
            if not is_weekend and is_5x2:
                weight -= 100_000.0

            try:
                id_val = int(d_id)
            except:
                id_val = d_id

            return (weight, id_val)

        assigned_drivers.sort(key=smart_sort_key)
        free_drivers.sort(key=smart_sort_key)

        trams_list = schedule.trams if isinstance(schedule.trams, list) else []

        def tram_sort_key(t):
            val = str(t.number)
            return (0, int(val)) if val.isdigit() else (1, val)

        sorted_trams = sorted(trams_list, key=tram_sort_key)

        tram_map = {}
        earliest_start_dt = base_dt + timedelta(hours=23, minutes=59)
        for tram in sorted_trams:
            tram_map[tram.number] = {"tram_number": tram.number, "shift_1": None, "shift_2": None, "issues": []}
            if tram.shift_1:
                start = self._combine_dt(base_dt, tram.shift_1.start)
                if start < earliest_start_dt: earliest_start_dt = start
        if earliest_start_dt > base_dt + timedelta(hours=20): earliest_start_dt = base_dt + timedelta(hours=5)

        worked_drivers_ids = set()

        def process_single_shift(tram_obj, shift_data, shift_name):
            if not shift_data: return
            s_start = self._combine_dt(base_dt, shift_data.start)
            s_end = self._combine_dt(base_dt, shift_data.end)
            if s_end < s_start: s_end += timedelta(days=1)
            s_dur = (s_end - s_start).total_seconds() / 3600.0

            # 1. Штатный поиск
            cand, src, warns, rest = self._find_candidate([assigned_drivers], day_of_month, shift_name, s_start, s_dur,
                                                          mode, daily_history_buffer, target_year, target_month)

            if not cand:
                cand, src, warns, rest = self._find_candidate([free_drivers], day_of_month, shift_name, s_start, s_dur,
                                                              mode, daily_history_buffer, target_year, target_month)
                if cand: src = "recruit"

            # 2. Овертайм (Только Real)
            if not cand and mode == "real":
                cand, src, warns, rest = self._find_overtime_candidate([assigned_drivers + free_drivers], day_of_month,
                                                                       s_start, s_dur, daily_history_buffer,
                                                                       target_year, target_month)

            if cand:
                tram_map[tram_obj.number][f"shift_{shift_name}"] = {
                    "driver": str(cand.id), "work_hours": round(s_dur, 2), "rest_before": round(rest, 1),
                    "warnings": warns, "source": src
                }
                daily_history_buffer[str(cand.id)] = {"end_dt": s_end, "duration": s_dur}
                worked_drivers_ids.add(str(cand.id))
                self.accumulated_hours[str(cand.id)] = self.accumulated_hours.get(str(cand.id), 0.0) + s_dur
            else:
                tram_map[tram_obj.number]["issues"].append(f"Нет водителя ({shift_name})")

        for tram in sorted_trams: process_single_shift(tram, tram.shift_1, "1")
        for tram in sorted_trams: process_single_shift(tram, tram.shift_2, "2")

        driver_stat_flags = {}
        for drv in assigned_drivers:
            d_id = str(drv.id)
            if d_id in worked_drivers_ids: continue
            plan = drv.get_status_for_day(day_of_month)
            if str(plan) in ["1", "2"]:
                driver_stat_flags[d_id] = "reserve"

        return {"date": day_of_month, "route": route_number, "roster": list(tram_map.values()),
                "driver_stat_flags": driver_stat_flags}

    def _find_candidate(self, groups, day, target_shift, start, dur, mode, daily_buffer, year, month):
        for drivers in groups:
            for d in drivers:
                d_id = str(d.id)
                if d_id in daily_buffer: continue

                # Проверка графика
                if str(d.get_status_for_day(day)) != str(target_shift): continue

                curr = self.accumulated_hours.get(d_id, 0.0)
                norm = self._get_driver_norm(d, year, month)

                # Лимит: Норма + HARD LIMIT (берем из конфига)
                limit = norm + (config.OVERTIME_HARD_LIMIT if mode == "real" else 0)

                if curr + dur > limit: continue

                can_work, rest, warns = self._check_rest_rules(d, start, mode)
                if not can_work: continue

                return d, "main", warns, rest
        return None, None, [], 0

    def _find_overtime_candidate(self, groups, day, start, dur, daily_buffer, year, month):
        for drivers in groups:
            for d in drivers:
                d_id = str(d.id)
                if d_id in daily_buffer: continue

                curr = self.accumulated_hours.get(d_id, 0.0)
                norm = self._get_driver_norm(d, year, month)

                # Лимит Овертайма: тоже берем из конфига
                limit = norm + config.OVERTIME_HARD_LIMIT
                if curr + dur > limit: continue

                can_work, rest, warns = self._check_rest_rules(d, start, "real")
                if not can_work: continue

                warns.append("Работа в выходной")
                return d, "overtime", warns, rest
        return None, None, [], 0

    def _check_rest_rules(self, driver, start_dt, mode):
        d_id = str(driver.id)
        last = self.history.get(d_id)
        if not last: return True, 999.0, []

        end_dt = last['end_dt']
        if isinstance(end_dt, str): end_dt = datetime.fromisoformat(end_dt)

        gap = (start_dt - end_dt).total_seconds() / 3600.0
        if gap < 0: return False, gap, ["Накладка"]

        warns = []
        is_ok = True

        if mode == "strict":
            # STRICT: используем настройки из конфига
            required = max(config.REST_MIN_HOURS_STRICT, config.REST_MULTIPLIER_STRICT * last['duration'])
            if gap < required: is_ok = False
        else:
            # REAL: используем настройки из конфига
            if gap < config.REST_MIN_HOURS_REAL:
                is_ok = False
            # Предупреждение, если меньше строгого правила
            elif gap < (config.REST_MULTIPLIER_STRICT * last['duration']):
                warns.append("(!)")

        return is_ok, gap, warns

    def _combine_dt(self, base, time_str):
        try:
            h, m = map(int, time_str.split(':'))
            return base + timedelta(hours=h, minutes=m)
        except:
            return base