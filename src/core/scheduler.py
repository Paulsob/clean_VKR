import json
import os
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Tuple

from src.utils import get_day_type_by_date
from src.constants import get_month_number
import src.config as config

sched_logger = logging.getLogger("src.core.scheduler")
if not sched_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | scheduler | %(message)s'))
    sched_logger.addHandler(handler)


class WorkforceAnalyzer:
    WEEKLY_REST_HOURS = 42.0

    def __init__(self, db):
        self.db = db
        self.history: Dict[str, Dict[str, Any]] = {}
        self.accumulated_hours: Dict[str, float] = {}
        self.norms = {}
        self._load_norms()

    def _load_norms(self):
        data_dir = getattr(config, 'DATA_DIR', 'data')
        possible_paths = [
            os.path.join(data_dir, "norms_2026.json"),
            "env_synthetic/data/norms_2026.json",
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
            k: {
                'end_dt': v['end_dt'].isoformat() if isinstance(v['end_dt'], datetime) else v['end_dt'],
                'duration': v['duration'],
                'rest_reductions': v.get('rest_reductions', 0)
            }
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
                    except ValueError:
                        pass
                if isinstance(end, str):
                    try:
                        end = datetime.strptime(end, "%Y-%m-%d").date()
                    except ValueError:
                        pass
                if isinstance(start, date) and isinstance(end, date) and start <= check_date <= end:
                    return True, reason
        return False, None

    def generate_daily_roster_for_all_routes(self, routes_list: List[str], day_of_month: int, target_month: str,
                                             target_year: int, mode: str = "real"):
        daily_history_buffer = {}
        results_by_route = {}

        priority_order = ["9", "20", "21", "47", "48", "55", "61"]
        sorted_routes = sorted(routes_list, key=lambda x: priority_order.index(x) if x in priority_order else 999)

        for route in sorted_routes:
            result = self._generate_single_route_roster(
                route, day_of_month, target_month, target_year, mode, daily_history_buffer
            )
            results_by_route[route] = result

        self.history.update(daily_history_buffer)
        return results_by_route

    def _generate_single_route_roster(self, route_number: str, day_of_month: int, target_month: str, target_year: int,
                                      mode: str, daily_history_buffer: Dict[str, Any]):
        current_day_type = get_day_type_by_date(day_of_month, target_month, year=target_year)
        m_num = get_month_number(target_month)
        current_date = date(target_year, m_num, day_of_month)
        base_dt = datetime(target_year, m_num, day_of_month)
        log_prefix = f"[R{route_number} D{day_of_month:02d}]"

        schedule = next((s for s in self.db.schedules if
                         str(s.route_number) == str(route_number) and s.day_type.lower() == current_day_type), None)
        if not schedule:
            return {"date": day_of_month, "route": route_number, "roster": [], "driver_stat_flags": {}}

        trams_list = schedule.trams if isinstance(schedule.trams, list) else []

        def tram_sort_key(t):
            return (0, int(str(t.number))) if str(t.number).isdigit() else (1, str(t.number))

        sorted_trams = sorted(trams_list, key=tram_sort_key)


        assigned_drivers = []
        free_drivers = []

        for d in self.db.drivers:
            if hasattr(d, 'month') and getattr(d, 'month') != target_month: continue
            is_absent, _ = self.is_driver_absent(d.id, current_date)
            if is_absent: continue

            allowed_routes = getattr(d, 'allowed_routes', ["ALL"])
            if "ALL" not in allowed_routes and str(route_number) not in allowed_routes: continue

            r_num = str(d.assigned_route_number) if getattr(d, 'assigned_route_number', None) else None
            if r_num == str(route_number):
                assigned_drivers.append(d)
            elif r_num in [None, "", "None", "0", "ANY"]:
                free_drivers.append(d)


        def packing_sort_key(driver):
            d_id = str(driver.id)
            hours = self.accumulated_hours.get(d_id, 0.0)
            norm = self._get_driver_norm(driver, target_year, target_month)

            if hours == 0.0:
                weight = 1000.0
            elif hours < norm:
                weight = -hours
            else:
                weight = 500.0 + hours

            try:
                id_val = int(d_id)
            except ValueError:
                id_val = d_id
            return (weight, id_val)

        assigned_drivers.sort(key=packing_sort_key)
        free_drivers.sort(key=packing_sort_key)

        tram_map = {}
        for tram in sorted_trams:
            tram_map[tram.number] = {"tram_number": tram.number, "shift_1": None, "shift_2": None, "issues": []}

        worked_drivers_ids = set()

        def process_single_shift(tram_obj, shift_data, shift_name):
            if not shift_data: return
            s_start = self._combine_dt(base_dt, shift_data.start)
            s_end = self._combine_dt(base_dt, shift_data.end)
            if s_end < s_start: s_end += timedelta(days=1)
            s_dur = (s_end - s_start).total_seconds() / 3600.0
            shift_id = f"T{tram_obj.number}/S{shift_name}"

            tram_model = str(
                getattr(tram_obj, 'tram_type', getattr(tram_obj, 'model', getattr(tram_obj, 'type', 'ALL'))))

            def filter_by_tram(drivers_list):
                return [d for d in drivers_list if
                        "ALL" in getattr(d, 'allowed_trams', ["ALL"]) or tram_model in getattr(d, 'allowed_trams',
                                                                                               ["ALL"])]

            val_assign = filter_by_tram(assigned_drivers)
            val_free = filter_by_tram(free_drivers)

            cand, src, warns, rest, new_reductions = None, None, [], 0, 0

            cand, src, warns, rest, new_reductions = self._find_candidate(val_assign, day_of_month, shift_name, s_start,
                                                                          s_dur, mode, daily_history_buffer,
                                                                          target_year, target_month)
            if cand: src = "assigned"

            if not cand:
                cand, src, warns, rest, new_reductions = self._find_candidate(val_free, day_of_month, shift_name,
                                                                              s_start, s_dur, mode,
                                                                              daily_history_buffer, target_year,
                                                                              target_month)
                if cand: src = "free"

            if cand:
                tram_map[tram_obj.number][f"shift_{shift_name}"] = {
                    "driver": str(cand.id), "work_hours": round(s_dur, 2), "rest_before": round(rest, 1),
                    "warnings": warns, "source": src
                }
                daily_history_buffer[str(cand.id)] = {"end_dt": s_end, "duration": s_dur,
                                                      "rest_reductions": new_reductions}
                worked_drivers_ids.add(str(cand.id))
                self.accumulated_hours[str(cand.id)] = self.accumulated_hours.get(str(cand.id), 0.0) + s_dur
            else:
                tram_map[tram_obj.number]["issues"].append(f"Нет водителя ({shift_name})")
                sched_logger.warning(f"{log_prefix} {shift_id} ДЫРА!")

        for tram in sorted_trams: process_single_shift(tram, tram.shift_1, "1")
        for tram in sorted_trams: process_single_shift(tram, tram.shift_2, "2")

        driver_stat_flags = {str(d.id): "reserve" for d in assigned_drivers if
                             str(d.id) not in worked_drivers_ids and str(d.get_status_for_day(day_of_month)) in ["1",
                                                                                                                 "2",
                                                                                                                 "Р",
                                                                                                                 "Я"]}

        return {"date": day_of_month, "route": route_number, "roster": list(tram_map.values()),
                "driver_stat_flags": driver_stat_flags}


    def _find_candidate(self, pool, day, target_shift, start, dur, mode, daily_buffer, year, month):
        max_shift = config.WORK_MAX_HOURS_EXTENDED if mode == "real" else config.WORK_MAX_HOURS_STANDARD
        if dur > max_shift or dur < config.WORK_MIN_HOURS: return None, None, [], 0, 0

        for d in pool:
            d_id = str(d.id)
            if d_id in daily_buffer: continue

            status = str(d.get_status_for_day(day)).upper().strip()
            if status not in [str(target_shift), "Р", "Я", "WORK", "S", "-1"]:
                continue

            curr = self.accumulated_hours.get(d_id, 0.0)
            norm = self._get_driver_norm(d, year, month)
            limit = norm + (config.OVERTIME_HARD_LIMIT if mode == "real" else 0)

            if curr + dur > limit:
                continue

            can_work, rest, warns, new_reductions = self._check_rest_rules(d, start, mode)
            if not can_work:
                continue

            return d, "main", warns, rest, new_reductions

        return None, None, [], 0, 0

    def _check_rest_rules(self, driver, start_dt, mode):
        d_id = str(driver.id)
        last = self.history.get(d_id)
        if not last: return True, 999.0, [], 0

        end_dt = last['end_dt']
        if isinstance(end_dt, str): end_dt = datetime.fromisoformat(end_dt)

        last_dur = last['duration']
        current_reductions = last.get('rest_reductions', 0)
        gap = (start_dt - end_dt).total_seconds() / 3600.0

        if gap < 0:
            return False, gap, ["Накладка"], current_reductions

        if gap >= self.WEEKLY_REST_HOURS: return True, gap, [], 0

        warns = []
        is_ok = True
        new_reductions = current_reductions
        req_standard = config.REST_MULTIPLIER * last_dur
        req_reduced = config.REST_MIN_REDUCED
        limit_reductions = config.REST_REDUCTIONS_LIMIT_REAL if mode == "real" else config.REST_REDUCTIONS_LIMIT_STRICT

        if gap >= req_standard:
            pass
        elif gap >= req_reduced:
            if current_reductions < limit_reductions:
                new_reductions += 1
                if mode != "strict": warns.append(f"Сокращенный отдых: {round(gap, 1)}ч")
            else:
                if mode == "strict":
                    is_ok = False
                else:
                    warns.append(f"Лимит сокращений ({limit_reductions}) превышен!")
                    new_reductions += 1
        else:
            is_ok = False
            warns.append(f"Отдых меньше {req_reduced}ч")

        return is_ok, gap, warns, new_reductions

    def _combine_dt(self, base, time_str):
        try:
            h, m = map(int, time_str.split(':'))
            return base + timedelta(hours=h, minutes=m)
        except ValueError:
            return base