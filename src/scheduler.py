from datetime import datetime, timedelta, time
from typing import List, Dict, Tuple, Optional
from src.utils import get_day_type_by_date, get_weekday_name


class WorkforceAnalyzer:
    def __init__(self, db):
        self.db = db
        # История: { driver_id: { 'end_dt': datetime, 'duration': float } }
        self.history = {}

    def load_history(self, history_data: dict):
        """Загрузить внешнюю историю (например, из прошлого месяца)"""
        self.history = history_data

    def generate_daily_roster(self, route_number: str, day_of_month: int,
                              target_month: str, target_year: int, mode: str = "real"):
        """
        Главный метод генерации наряда на день.
        mode:
          - 'strict': Водитель пропускается при нарушении отдыха.
          - 'real': Водитель назначается, но с пометкой warning.
        """
        # 1. Поиск расписания
        current_day_type = get_day_type_by_date(day_of_month, target_month, year=target_year)
        schedule = next((s for s in self.db.schedules if
                         str(s.route_number) == str(route_number) and
                         s.day_type.lower() == current_day_type), None)

        if not schedule: return {"error": f"Нет расписания ({current_day_type})"}

        # 2. Списки водителей
        main_drivers = [d for d in self.db.drivers if
                        str(d.assigned_route_number) == str(route_number) and d.month == target_month]
        reserve_drivers = [d for d in self.db.drivers if
                           str(d.assigned_route_number) == "ANY" and d.month == target_month]

        # 3. Подготовка
        roster = []
        month_map = {
            "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6,
            "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12
        }
        m_num = month_map.get(target_month, 2)
        current_date = datetime(target_year, m_num, day_of_month)

        # Сортируем вагоны по номеру (можно по времени выхода)
        sorted_trams = sorted(schedule.trams, key=lambda t: t.number)

        for tram in sorted_trams:
            tram_res = {
                "tram_number": tram.number,
                "shift_1": {"driver": None, "warnings": []},
                "shift_2": {"driver": None, "warnings": []},
                "issues": []
            }

            # === СМЕНА 1 (УТРО) ===
            if tram.shift_1:
                # ЗАГЛУШКА ВРЕМЕНИ (Пока нет точных данных в tram)
                s_start = current_date + timedelta(hours=5)  # 05:00
                s_dur = 8.0

                cand, src, warns = self._find_candidate(
                    [main_drivers, reserve_drivers],
                    day_of_month, "1", s_start, s_dur, mode
                )

                if cand:
                    tram_res["shift_1"]["driver"] = f"{cand.id}" + (" (Рез)" if src == "reserve" else "")
                    tram_res["shift_1"]["warnings"] = warns
                    self.history[str(cand.id)] = {
                        'end_dt': s_start + timedelta(hours=s_dur),
                        'duration': s_dur
                    }
                    if src == "main":
                        main_drivers.remove(cand)
                    else:
                        reserve_drivers.remove(cand)
                else:
                    tram_res["issues"].append("Нет водителя (утро)")

            # === СМЕНА 2 (ВЕЧЕР) ===
            if tram.shift_2:
                s_start = current_date + timedelta(hours=14)  # 14:00
                s_dur = 8.0

                cand, src, warns = self._find_candidate(
                    [main_drivers, reserve_drivers],
                    day_of_month, "2", s_start, s_dur, mode
                )

                if cand:
                    tram_res["shift_2"]["driver"] = f"{cand.id}" + (" (Рез)" if src == "reserve" else "")
                    tram_res["shift_2"]["warnings"] = warns
                    self.history[str(cand.id)] = {
                        'end_dt': s_start + timedelta(hours=s_dur),
                        'duration': s_dur
                    }
                    if src == "main":
                        main_drivers.remove(cand)
                    else:
                        reserve_drivers.remove(cand)
                else:
                    tram_res["issues"].append("Нет водителя (вечер)")

            roster.append(tram_res)

        return {
            "date": day_of_month,
            "route": route_number,
            "roster": roster,
            "stats": {"leftover": len(main_drivers) + len(reserve_drivers)}
        }

    def _find_candidate(self, groups, day, target_shift_code, shift_start, shift_dur, mode):
        """
        Ищет подходящего водителя.
        Возвращает: (driver, source_type, warnings_list)
        """
        group_names = ["main", "reserve"]

        for i, drivers in enumerate(groups):
            source = group_names[i]
            # Сортировка внутри группы (опционально, для стабильности)
            # drivers.sort(key=lambda d: d.id)

            for driver in drivers:
                # 1. Проверка Табеля (Жесткая)
                status = driver.get_status_for_day(day)
                # Табель "1" ждет смену "1", табель "2" ждет смену "2"
                if status != target_shift_code:
                    continue

                # 2. Проверка Отдыха
                warnings = self._check_rest(driver.id, shift_start)

                if warnings:
                    if mode == "strict":
                        continue  # В строгом режиме пропускаем
                    # В режиме real берем, warning уже записан в переменную

                return driver, source, warnings

        return None, None, []

    def _check_rest(self, driver_id, current_start_dt) -> List[str]:
        """Расчет недоотдыха"""
        last_rec = self.history.get(str(driver_id))
        if not last_rec:
            return []  # Нет истории - значит отдыхал

        last_end = last_rec['end_dt']
        last_dur = last_rec['duration']

        # Разрыв в часах
        gap_hours = (current_start_dt - last_end).total_seconds() / 3600

        # Физическая невозможность (накладка)
        if gap_hours < 0:
            return ["Накладка смен!"]

        # Норма ежедневная
        required = max(12, 2 * last_dur)

        # Норма еженедельная (42ч)
        # Логика: если разрыв большой (>24ч), считаем, что это был выходной, и добавляем 42ч
        if gap_hours > 24:
            required += 42

        if gap_hours < required:
            return [f"Недоотдых: {gap_hours:.1f}ч вместо {required:.1f}ч"]

        return []