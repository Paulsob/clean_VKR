from datetime import datetime, timedelta, time
from typing import List, Dict, Optional, Tuple


class WorkforceAnalyzer:
    def __init__(self, db):
        self.db = db
        # { 'driver_id': {'last_end_dt': datetime, 'last_duration': float} }
        self.history: Dict[str, dict] = {}

    def load_history(self, history_data: dict):
        self.history = history_data

    def generate_daily_roster(self, route_number: str, day_of_month: int,
                              target_month: str, target_year: int, mode: str = "real"):

        # ... (импорты и поиск расписания - без изменений) ...
        from src.utils import get_day_type_by_date
        current_day_type = get_day_type_by_date(day_of_month, target_month, year=target_year)

        schedule = next((s for s in self.db.schedules if
                         str(s.route_number) == str(route_number) and s.day_type.lower() == current_day_type), None)
        if not schedule: return {"error": f"Нет расписания ({current_day_type})"}

        main_drivers = [d for d in self.db.drivers if
                        str(d.assigned_route_number) == str(route_number) and d.month == target_month]
        reserve_drivers = [d for d in self.db.drivers if
                           str(d.assigned_route_number) == "ANY" and d.month == target_month]

        # Сортировка вагонов (лучше по времени, но пока по номеру)
        sorted_trams = sorted(schedule.trams, key=lambda t: t.number)

        roster = []
        month_num = {"Январь": 1, "Февраль": 2, "Март": 3}.get(target_month, 1)
        # Базовая дата дня расчета
        current_date_base = datetime(target_year, month_num, day_of_month)

        for tram in sorted_trams:
            tram_result = {
                "tram_number": tram.number,
                "shift_1": {"driver": None, "warnings": []},
                "shift_2": {"driver": None, "warnings": []},
                "issues": []
            }

            # === 1 СМЕНА ===
            if tram.shift_1:
                # ПОПЫТАЙСЯ ВЗЯТЬ РЕАЛЬНОЕ ВРЕМЯ ИЗ tram
                # Если в tram есть атрибут start_time (строка "HH:MM" или time), используй его
                # s1_time = tram.shift_1_start_time if hasattr(tram, 'shift_1_start_time') else time(5, 0)

                s1_start = datetime.combine(current_date_base.date(), time(5, 0))
                s1_dur = 8.0

                cand, source, violations = self._select_best_driver(
                    [main_drivers, reserve_drivers], day_of_month, "morning",
                    s1_start, s1_dur
                )

                if cand:
                    tram_result["shift_1"]["driver"] = f"{cand.id}" + (" (Рез)" if source == "reserve" else "")
                    tram_result["shift_1"]["warnings"] = violations

                    # Пишем в историю
                    self.history[str(cand.id)] = {
                        "last_end_dt": s1_start + timedelta(hours=s1_dur),
                        "last_duration": s1_dur
                    }
                    if source == "main":
                        main_drivers.remove(cand)
                    else:
                        reserve_drivers.remove(cand)
                else:
                    # Если даже с нарушениями никого нет - значит табель пуст
                    tram_result["issues"].append("Нет доступных водителей в табеле")

            # === 2 СМЕНА ===
            if tram.shift_2:
                s2_start = datetime.combine(current_date_base.date(), time(14, 0))
                s2_dur = 8.0

                cand, source, violations = self._select_best_driver(
                    [main_drivers, reserve_drivers], day_of_month, "evening",
                    s2_start, s2_dur
                )

                if cand:
                    tram_result["shift_2"]["driver"] = f"{cand.id}" + (" (Рез)" if source == "reserve" else "")
                    tram_result["shift_2"]["warnings"] = violations

                    self.history[str(cand.id)] = {
                        "last_end_dt": s2_start + timedelta(hours=s2_dur),
                        "last_duration": s2_dur
                    }
                    if source == "main":
                        main_drivers.remove(cand)
                    else:
                        reserve_drivers.remove(cand)
                else:
                    tram_result["issues"].append("Нет доступных водителей в табеле")

            roster.append(tram_result)

        return {
            "date": day_of_month,
            "route": route_number,
            "roster": roster,
            "stats": {"leftover": len(main_drivers) + len(reserve_drivers)}
        }

    def _select_best_driver(self, driver_groups, day, shift_type, shift_start, shift_dur):
        """
        Теперь эта функция НИКОГДА не отфильтровывает водителя, если он есть в табеле.
        Она просто начисляет штрафы за усталость.
        """
        target_status = "1" if shift_type == "morning" else "2"
        group_names = ["main", "reserve"]
        candidates = []

        for i, drivers in enumerate(driver_groups):
            source = group_names[i]
            for driver in drivers:
                # 1. ЕДИНСТВЕННЫЙ ЖЕСТКИЙ ФИЛЬТР - ТАБЕЛЬ
                if driver.get_status_for_day(day) != target_status:
                    continue

                # Если водитель прошел этот check, он УЖЕ кандидат, даже если умирает от усталости.

                score = 0
                violations = []

                # 2. ПРОВЕРКА ОТДЫХА
                hist = self.history.get(str(driver.id))
                if hist:
                    last_end = hist['last_end_dt']
                    last_dur = hist['last_duration']

                    # Сколько времени прошло с конца прошлой смены до начала этой
                    hours_gap = (shift_start - last_end).total_seconds() / 3600

                    # Если gap отрицательный (накладка смен), это физически невозможно
                    if hours_gap < 0:
                        continue  # Это единственное исключение: человек не может быть в двух местах

                    # Норма ежедневная
                    daily_norm = max(12, 2 * last_dur)

                    # Определяем, нужен ли еженедельный отдых (42ч)
                    # Если разрыв большой (например, > 24ч), считаем, что это был выходной
                    # Правило: Если между сменами прошло больше 24 часов,
                    # мы ожидаем, что там "поместится" 42 часа + ежедневный.

                    is_weekly_rest_needed = hours_gap > 24

                    required_total = daily_norm
                    if is_weekly_rest_needed:
                        required_total += 42

                    # Проверка
                    if hours_gap < required_total:
                        shortage = required_total - hours_gap
                        violations.append(f"Недоотдых {shortage:.1f}ч (Факт: {hours_gap:.1f}, Норма: {required_total})")
                        score -= 1000  # Сильно понижаем приоритет, но НЕ УДАЛЯЕМ
                    else:
                        score += 50  # Бонус за то, что хорошо отдохнул

                # 3. Приоритет своим перед резервом
                if source == "main":
                    score += 100

                candidates.append((score, driver, source, violations))

        if not candidates:
            return None, None, []

        # Сортировка: Максимальный score -> Лучший кандидат
        candidates.sort(key=lambda x: x[0], reverse=True)

        best = candidates[0]
        return best[1], best[2], best[3]