import os
import sys
import json
import csv
import random
import time
import math
from datetime import date, timedelta, datetime

# Настройка путей
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import src.config as config
from src.prepare_data.database import DataLoader
from src.core.run_simulation import run_simulation_sequence
from src.analytics.driver_counter import DriverStatsCounter
from src.logger import get_logger

# Отключаем лишний шум в логах
import logging

logging.getLogger("src.prepare_data.database").setLevel(logging.WARNING)
logging.getLogger("src.core.scheduler").setLevel(logging.WARNING)
logging.getLogger("src.core.run_simulation").setLevel(logging.WARNING)
logging.getLogger("src.analytics.driver_counter").setLevel(logging.WARNING)

logger = get_logger("ExperimentRunner")


class ExperimentAbsenceGenerator:
    """
    Класс для программной генерации отсутствий (без input())
    с поддержкой сложных распределений.
    """

    def __init__(self):
        self.absences_file = os.path.join(config.DATA_DIR, "absences.json")
        self.loader = DataLoader(data_folder=config.DATA_DIR)

        # Глушим логи загрузчика
        logging.getLogger("src.prepare_data.database").setLevel(logging.CRITICAL)
        self.loader.load_all()

        # !!! ИСПРАВЛЕНИЕ 1: Сортируем список после set !!!
        # Это гарантирует, что список всегда будет ['1', '10', '2'...] в любом запуске
        self.driver_ids = sorted(list(set(str(d.id) for d in self.loader.drivers)),
                                 key=lambda x: int(x) if x.isdigit() else x)
        self.total_drivers = len(self.driver_ids)

    def clear_absences(self):
        """Полная очистка файла отсутствий"""
        with open(self.absences_file, "w", encoding="utf-8") as f:
            json.dump({"absences": []}, f)

    def save_absences(self, new_absences):
        """Сохранение списка"""
        with open(self.absences_file, "w", encoding="utf-8") as f:
            json.dump({"absences": new_absences}, f, indent=2, ensure_ascii=False)

    def generate(self, year: int, scenario_type: str):
        """
        Генерация на основе типа сценария.
        """
        # !!! ИСПРАВЛЕНИЕ 2: Фиксируем зерно генератора !!!
        # Теперь для сценария 'a' последовательность всегда будет идентичной
        # hash(scenario_type) нужен, чтобы сценарий 'b' отличался от 'a'
        random.seed(42 + sum(ord(c) for c in scenario_type))

        new_absences = []

        # 1. ГЕНЕРАЦИЯ ОТПУСКОВ
        VACATION_LEN = 28
        start_year = date(year, 1, 1)
        end_year = date(year, 12, 31)
        days_in_year = (end_year - start_year).days + 1

        # Создаем копию для шаффла, чтобы self.driver_ids остался чистым
        drivers_for_vacation = self.driver_ids[:]
        random.shuffle(drivers_for_vacation)

        for i, drv_id in enumerate(drivers_for_vacation):
            if scenario_type == 'e':
                # Сезонность
                if random.random() < 0.5:
                    offset = random.randint(151, 240)
                else:
                    offset = random.choice([
                        random.randint(0, 150),
                        random.randint(241, days_in_year - VACATION_LEN)
                    ])
            else:
                # Равномерно
                offset = int((i / self.total_drivers) * (days_in_year - VACATION_LEN))
                offset += random.randint(-5, 5)

            offset = max(0, min(offset, days_in_year - VACATION_LEN))

            vac_start = start_year + timedelta(days=offset)
            vac_end = vac_start + timedelta(days=VACATION_LEN - 1)

            new_absences.append({
                "driver_id": drv_id,
                "type": "vacation",
                "from": vac_start.strftime("%Y-%m-%d"),
                "to": vac_end.strftime("%Y-%m-%d"),
                "comment": f"Scen_{scenario_type}_Vac"
            })

        # 2. ГЕНЕРАЦИЯ БОЛЬНИЧНЫХ
        busy_map = {d_id: [] for d_id in self.driver_ids}
        for item in new_absences:
            d_s = datetime.strptime(item["from"], "%Y-%m-%d").date()
            d_e = datetime.strptime(item["to"], "%Y-%m-%d").date()
            busy_map[item["driver_id"]].append((d_s, d_e))

        current_date = start_year
        active_sick_leaves = []

        while current_date <= end_year:
            active_sick_leaves = [x for x in active_sick_leaves if x["end"] >= current_date]

            if scenario_type == 'a' or scenario_type == 'e':
                target_pct = 0.08
            elif scenario_type == 'b':
                target_pct = 0.0
            elif scenario_type == 'c':
                val = random.normalvariate(0.055, 0.025)
                target_pct = max(0.01, min(0.10, val))
            elif scenario_type == 'd':
                target_pct = random.uniform(0.00, 0.15)
            else:
                target_pct = 0.08

            target_count = int(self.total_drivers * target_pct)
            needed = target_count - len(active_sick_leaves)

            if needed > 0:
                # ВАЖНО: Используем sorted(self.driver_ids) как базу для выборки,
                # чтобы random.sample всегда работал детерминированно
                sample_size = min(len(self.driver_ids), needed * 3 + 20)
                candidates = random.sample(self.driver_ids, sample_size)

                added_today = 0
                for d_id in candidates:
                    if added_today >= needed: break

                    if any(x["id"] == d_id for x in active_sick_leaves): continue

                    is_busy = False
                    for b_start, b_end in busy_map[d_id]:
                        if b_start <= current_date <= b_end:
                            is_busy = True;
                            break
                    if is_busy: continue

                    dur = random.randint(5, 14)
                    s_end = current_date + timedelta(days=dur - 1)
                    if s_end > end_year: s_end = end_year

                    new_absences.append({
                        "driver_id": d_id,
                        "type": "sick",
                        "from": current_date.strftime("%Y-%m-%d"),
                        "to": s_end.strftime("%Y-%m-%d"),
                        "comment": f"Scen_{scenario_type}_Sick"
                    })

                    active_sick_leaves.append({"id": d_id, "end": s_end})
                    busy_map[d_id].append((current_date, s_end))
                    added_today += 1

            current_date += timedelta(days=1)

        self.save_absences(new_absences)


def run_experiments():
    output_file = os.path.join(config.OUTPUTS_DIR, "EXPERIMENT_RESULTS.csv")

    # Параметры экспериментов
    PATTERNS = ["3x2x3x1"]
    DURATIONS = [1, 3, 12]
    SCENARIOS = {
        'a': "A: Sick 8%, Vac 1/12",
        'b': "B: Sick 0%, Vac 1/12",
        'c': "C: Sick Normal(1-10%), Vac 1/12",
        'd': "D: Sick Rand(0-15%), Vac 1/12",
        'e': "E: Sick 8%, Vac Seasonal(Sum 15%)"
    }
    # Подготовка CSV
    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Pattern", "Duration (Months)", "Scenario Code", "Scenario Desc", "Total Drivers Used"])

    # Инициализация генератора
    print("Инициализация генератора отсутствий...")
    # ВАЖНО: Нужно временно подменить config, чтобы генератор загрузил правильных водителей
    # Но так как drivers_json зависят от pattern, придется пересоздавать генератор внутри цикла
    # или (лучше) просто загрузить ВСЕХ водителей один раз?
    # Нет, лучше создавать генератор под каждый паттерн.

    total_experiments = len(PATTERNS) * len(DURATIONS) * len(SCENARIOS)
    curr_exp = 0

    print(f"=== ЗАПУСК {total_experiments} ЭКСПЕРИМЕНТОВ ===")

    start_time_global = time.time()

    for pat in PATTERNS:
        # 1. Настройка конфига под паттерн
        config.SELECTED_PATTERN = pat
        config.USE_SYNTHETIC_DATA = True

        # Обновляем пути в конфиге (костыль, т.к. они вычисляются при импорте)
        config.RESULTS_DIR = os.path.join(config.DATA_DIR, "results", pat)
        if not os.path.exists(config.RESULTS_DIR):
            os.makedirs(config.RESULTS_DIR)

        # 2. Инициализируем генератор для этого паттерна
        # (он загрузит водителей из папки паттерна)
        abs_gen = ExperimentAbsenceGenerator()

        # 3. Загружаем базу для симуляции
        db = DataLoader()
        db.load_all()  # Загрузит водителей, расписания и т.д.

        # Определяем маршруты (все)
        routes = sorted(list(set(str(s.route_number) for s in db.schedules)))

        for dur in DURATIONS:
            for scen_code, scen_desc in SCENARIOS.items():
                curr_exp += 1
                print(f"\n[{curr_exp}/{total_experiments}] Паттерн: {pat} | Срок: {dur} мес | Сценарий: {scen_code}")

                # А. Очистка и Генерация отсутствий
                abs_gen.clear_absences()
                abs_gen.generate(year=2026, scenario_type=scen_code)

                # Перезагружаем отсутствия в db (важно!)
                db._load_absences()

                # Б. Запуск симуляции
                # Глушим вывод полностью на время симуляции
                try:
                    run_simulation_sequence(
                        routes_list=routes,
                        db=db,
                        start_month="Январь",
                        start_year=2026,
                        duration=dur,
                        mode="strict"  # Или "real"
                    )
                except Exception as e:
                    logger.error(f"Ошибка симуляции: {e}")

                # В. Подсчет результатов
                analyzer = DriverStatsCounter()
                # Передаем параметры явно, т.к. config мог не обновиться полностью
                analyzer.base_results_dir = os.path.join(config.DATA_DIR, "results", pat)
                analyzer.pattern = pat

                count = analyzer.count_unique_drivers(
                    start_month="Январь",
                    start_year=2026,
                    duration_months=dur
                )

                print(f"--> Результат: {count} водителей")

                # Г. Запись в CSV
                with open(output_file, "a", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerow([pat, dur, scen_code, scen_desc, count])

    total_time = (time.time() - start_time_global) / 60
    print(f"\n=== ГОТОВО! Время выполнения: {total_time:.1f} мин ===")
    print(f"Файл результатов: {output_file}")


if __name__ == "__main__":
    run_experiments()
