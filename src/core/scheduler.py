from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
from src.utils import get_day_type_by_date


class WorkforceAnalyzer:
    def __init__(self, db):
        self.db = db
        self.history = {}

    def load_history(self, history_data: dict):
        self.history = {}
        for did, data in history_data.items():
            try:
                dt_val = datetime.fromisoformat(data['end_dt']) if isinstance(data['end_dt'], str) else data['end_dt']
                self.history[did] = {'end_dt': dt_val, 'duration': data['duration']}
            except:
                continue

    def get_history_serializable(self):
        return {k: {'end_dt': v['end_dt'].isoformat(), 'duration': v['duration']} for k, v in self.history.items()}

    def is_driver_absent(self, driver_id: str, check_date: date) -> tuple:
        """
        Проверяет, отсутствует ли водитель в указанную дату.
        Возвращает: (True/False, причина)
        """
        for absence in self.db.absences:
            if absence["driver_id"] == str(driver_id):
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
        # -----------------------------
        # Тип дня и расписание
        # -----------------------------
        current_day_type = get_day_type_by_date(
            day_of_month, target_month, year=target_year
        )

        schedule = next(
            (
                s for s in self.db.schedules
                if str(s.route_number) == str(route_number)
                   and s.day_type.lower() == current_day_type
            ),
            None
        )

        if not schedule:
            return {"error": f"Нет расписания ({current_day_type})"}

        # -----------------------------
        # Дата
        # -----------------------------
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

        # -----------------------------
        # Формируем списки водителей
        # -----------------------------
        main_drivers = []
        reserve_drivers = []

        for d in self.db.drivers:
            if d.month != target_month:
                continue

            is_absent, _ = self.is_driver_absent(d.id, current_date)
            if is_absent:
                continue

            route = str(d.assigned_route_number).strip()

            if route == str(route_number):
                main_drivers.append(d)
            elif route.upper() == "ANY":
                reserve_drivers.append(d)

        # -----------------------------
        # Трамваи
        # -----------------------------
        try:
            sorted_trams = sorted(
                schedule.trams,
                key=lambda t: int(t.number)
                if str(t.number).isdigit()
                else t.number
            )
        except Exception:
            sorted_trams = schedule.trams

        # -----------------------------
        # Заготовка результата
        # -----------------------------
        tram_map = {}

        for tram in sorted_trams:
            tram_map[tram.number] = {
                "tram_number": tram.number,
                "shift_1": None,
                "shift_2": None,
                "issues": []
            }

        # =====================================================
        # СМЕНА 1 — ДЛЯ ВСЕХ ТРАМВАЕВ
        # =====================================================
        for tram in sorted_trams:
            if not tram.shift_1:
                continue

            s_start = tram.shift_1.start
            s_end = tram.shift_1.end

            s_start_dt = self._combine_dt(base_dt, s_start)
            s_end_dt = self._combine_dt(base_dt, s_end)
            if s_end_dt < s_start_dt:
                s_end_dt += timedelta(days=1)

            s_dur = (s_end_dt - s_start_dt).total_seconds() / 3600

            cand, src, warns, rest_val = self._find_candidate(
                [main_drivers, reserve_drivers],
                day_of_month,
                "1",
                s_start_dt,
                s_dur,
                mode
            )

            if cand:
                tram_map[tram.number]["shift_1"] = {
                    "driver": f"{cand.id}" + (" (Рез)" if src == "reserve" else ""),
                    "work_hours": round(s_dur, 2),
                    "rest_before": rest_val,
                    "warnings": warns,
                    "time_range": f"{s_start}-{s_end}"
                }

                self.history[str(cand.id)] = {
                    "end_dt": s_end_dt,
                    "duration": s_dur
                }

                self._remove_driver(cand, main_drivers, reserve_drivers)
            else:
                tram_map[tram.number]["issues"].append("Нет водителя (утро)")

        # =====================================================
        # СМЕНА 2 — ДЛЯ ВСЕХ ТРАМВАЕВ
        # =====================================================
        for tram in sorted_trams:
            if not tram.shift_2:
                continue

            s_start = tram.shift_2.start
            s_end = tram.shift_2.end

            s_start_dt = self._combine_dt(base_dt, s_start)
            s_end_dt = self._combine_dt(base_dt, s_end)
            if s_end_dt < s_start_dt:
                s_end_dt += timedelta(days=1)

            s_dur = (s_end_dt - s_start_dt).total_seconds() / 3600

            cand, src, warns, rest_val = self._find_candidate(
                [main_drivers, reserve_drivers],
                day_of_month,
                "2",
                s_start_dt,
                s_dur,
                mode
            )

            if cand:
                tram_map[tram.number]["shift_2"] = {
                    "driver": f"{cand.id}" + (" (Рез)" if src == "reserve" else ""),
                    "work_hours": round(s_dur, 2),
                    "rest_before": rest_val,
                    "warnings": warns,
                    "time_range": f"{s_start}-{s_end}"
                }

                self.history[str(cand.id)] = {
                    "end_dt": s_end_dt,
                    "duration": s_dur
                }

                self._remove_driver(cand, main_drivers, reserve_drivers)
            else:
                tram_map[tram.number]["issues"].append("Нет водителя (вечер)")

        # -----------------------------
        # Финальный результат
        # -----------------------------
        roster = list(tram_map.values())

        return {
            "date": day_of_month,
            "route": route_number,
            "roster": roster
        }

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

    def _find_candidate(self, groups, day, target_shift, shift_start, shift_dur, mode):
        group_names = ["main", "reserve"]
        for i, drivers in enumerate(groups):
            source = group_names[i]
            for driver in drivers:
                if driver.get_status_for_day(day) != target_shift:
                    continue
                warnings, rest_fact = self._check_rest(driver.id, shift_start)
                if warnings and mode == "strict":
                    continue
                return driver, source, warnings, rest_fact
        return None, None, [], 0

    def _check_rest(self, driver_id, current_start_dt):
        last_rec = self.history.get(str(driver_id))
        if not last_rec: return [], 999.0
        last_end = last_rec['end_dt']
        last_dur = last_rec['duration']
        gap_hours = (current_start_dt - last_end).total_seconds() / 3600
        if gap_hours < 0: return ["Накладка"], gap_hours
        required = max(12, 2 * last_dur)
        if gap_hours > 24: required += 42
        warns = []
        if gap_hours < required:
            warns.append(f"Недоотдых")
        return warns, gap_hours