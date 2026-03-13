import os
import sys
import json
import csv
import random
import time
import glob
from datetime import date, timedelta, datetime

# Настройка путей
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import src.config as config
from src.prepare_data.database import DataLoader
from src.core.run_simulation import run_simulation_sequence
from src.constants import get_month_number

# Отключаем лишний шум в логах
import logging

logging.getLogger("src.prepare_data.database").setLevel(logging.CRITICAL)
logging.getLogger("src.core.scheduler").setLevel(logging.CRITICAL)
logging.getLogger("src.core.run_simulation").setLevel(logging.CRITICAL)


class ExperimentAbsenceGenerator:
    def __init__(self):
        self.absences_file = os.path.join(config.DATA_DIR, "absences.json")
        self.loader = DataLoader(data_folder=config.DATA_DIR)
        self.loader.load_all()

        # Фиксируем сортировку ID для воспроизводимости
        self.driver_ids = sorted(list(set(str(d.id) for d in self.loader.drivers)),
                                 key=lambda x: int(x) if x.isdigit() else x)
        self.total_drivers = len(self.driver_ids)

    def clear_absences(self):
        with open(self.absences_file, "w", encoding="utf-8") as f:
            json.dump({"absences": []}, f)

    def save_absences(self, new_absences):
        with open(self.absences_file, "w", encoding="utf-8") as f:
            json.dump({"absences": new_absences}, f, indent=2, ensure_ascii=False)

    def generate(self, year: int, scenario_type: str):
        random.seed(42 + ord(scenario_type))
        new_absences = []

        # === СЦЕНАРИЙ 2: 0% больных, 0 отпусков ===
        if scenario_type == '2':
            self.save_absences([])
            return

        # === ГЕНЕРАЦИЯ ОТПУСКОВ ===
        VACATION_LEN = 28
        start_year = date(year, 1, 1)
        end_year = date(year, 12, 31)
        days_in_year = (end_year - start_year).days + 1

        drivers_for_vacation = self.driver_ids[:]
        random.shuffle(drivers_for_vacation)

        for i, drv_id in enumerate(drivers_for_vacation):
            if scenario_type == '5':
                # Пик в летние месяцы: 45% отпусков сбрасываем в июнь-июль-август (в 3 раза плотнее, чем обычно)
                # Это даст примерно 15% одновременно отдыхающих в Июле.
                if random.random() < 0.45:
                    offset = random.randint(152, 243)  # Летние дни
                else:
                    offset = random.choice([
                        random.randint(0, 150),
                        random.randint(244, days_in_year - VACATION_LEN)
                    ])
            else:
                # Равномерно (1/12 в месяц)
                offset = int((i / self.total_drivers) * (days_in_year - VACATION_LEN))
                offset += random.randint(-5, 5)

            offset = max(0, min(offset, days_in_year - VACATION_LEN))
            vac_start = start_year + timedelta(days=offset)
            vac_end = vac_start + timedelta(days=VACATION_LEN - 1)

            new_absences.append({
                "driver_id": drv_id, "type": "vacation",
                "from": vac_start.strftime("%Y-%m-%d"), "to": vac_end.strftime("%Y-%m-%d"),
                "comment": f"Scen_{scenario_type}_Vac"
            })

        # === ГЕНЕРАЦИЯ БОЛЬНИЧНЫХ ===
        busy_map = {d_id: [] for d_id in self.driver_ids}
        for item in new_absences:
            d_s = datetime.strptime(item["from"], "%Y-%m-%d").date()
            d_e = datetime.strptime(item["to"], "%Y-%m-%d").date()
            busy_map[item["driver_id"]].append((d_s, d_e))

        current_date = start_year
        active_sick_leaves = []

        while current_date <= end_year:
            active_sick_leaves = [x for x in active_sick_leaves if x["end"] >= current_date]

            # Определение процента заболевших по сценарию
            if scenario_type in ['1', '5']:
                target_pct = 0.08  # Строго 8%
            elif scenario_type == '3':
                # Нормальное распределение от 1% до 10%
                val = random.normalvariate(0.055, 0.025)
                target_pct = max(0.01, min(0.10, val))
            elif scenario_type == '4':
                # Случайным образом до 15%
                target_pct = random.uniform(0.00, 0.15)
            else:
                target_pct = 0.0

            target_count = int(self.total_drivers * target_pct)
            needed = target_count - len(active_sick_leaves)

            if needed > 0:
                sample_size = min(len(self.driver_ids), needed * 3 + 20)
                candidates = random.sample(self.driver_ids, sample_size)

                added_today = 0
                for d_id in candidates:
                    if added_today >= needed: break
                    if any(x["id"] == d_id for x in active_sick_leaves): continue

                    is_busy = False
                    for b_start, b_end in busy_map[d_id]:
                        if b_start <= current_date <= b_end:
                            is_busy = True
                            break
                    if is_busy: continue

                    dur = random.randint(5, 14)
                    s_end = current_date + timedelta(days=dur - 1)
                    if s_end > end_year: s_end = end_year

                    new_absences.append({
                        "driver_id": d_id, "type": "sick",
                        "from": current_date.strftime("%Y-%m-%d"), "to": s_end.strftime("%Y-%m-%d"),
                        "comment": f"Scen_{scenario_type}_Sick"
                    })

                    active_sick_leaves.append({"id": d_id, "end": s_end})
                    busy_map[d_id].append((current_date, s_end))
                    added_today += 1

            current_date += timedelta(days=1)

        self.save_absences(new_absences)


def count_drivers_in_results(month, year, mode):
    """Считает уникальных водителей напрямую из JSON-файлов результатов"""
    m_num = get_month_number(month)
    dir_name = f"{m_num:02d}_{month}_{year}"
    target_dir = os.path.join(config.RESULTS_DIR, dir_name, mode)

    search_pattern = os.path.join(target_dir, f"simulation_{mode}_*_{month}_{year}.json")
    found_files = glob.glob(search_pattern)

    unique_drivers = set()
    for file_path in found_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for day_key, day_data in data.items():
                    if not day_key.isdigit(): continue
                    for tram in day_data.get('roster', []):
                        for shift in ['shift_1', 'shift_2']:
                            info = tram.get(shift)
                            if info and info.get('driver'):
                                d_id = str(info['driver']).split()[0]
                                unique_drivers.add(d_id)
        except Exception:
            pass

    return len(unique_drivers)


def run_experiments():
    # Названия сценариев, как вы просили
    SCENARIOS = {
        '1': ("8% больных, 1/12 отпускных", "Январь"),
        '2': ("0% больных, 0 отпускных", "Январь"),
        '3': ("1-10% больных (нормальное распр.), 1/12 отпускных", "Январь"),
        '4': ("Случайные больничные до 15%, 1/12 отпускных", "Январь"),
        '5': ("Летний пик отпусков (до 15%), 8% больных", "Июль")  # Симулируем Июль, чтобы поймать пик!
    }

    print("=== ИНИЦИАЛИЗАЦИЯ ЭКСПЕРИМЕНТА ===")

    # 1. Принудительные настройки для чистоты эксперимента
    config.SIMULATION_MODE = "real"  # Как вы просили в прошлых диалогах (смешивание и овертаймы)
    config.PROCESS_ALL_ROUTES = True  # Считаем для всего парка

    # Имя папки, где лежат ваши смешанные графики 4х2 и 5х2 (подставьте нужное, если отличается)
    pat = getattr(config, 'SIMULATION_SCENARIO_NAME', "mix_optimization_v1")
    config.RESULTS_DIR = os.path.join(config.DATA_DIR, "results", pat)
    os.makedirs(config.RESULTS_DIR, exist_ok=True)

    # 2. Инициализируем генератор и БД
    abs_gen = ExperimentAbsenceGenerator()
    db = DataLoader()
    db.load_all()
    routes = sorted(list(set(str(s.route_number) for s in db.schedules)))

    results = {}
    start_time_global = time.time()

    print(f"🚌 Анализ пула: Смешанный график ({pat}). Маршрутов: {len(routes)}.")
    print("-" * 75)

    for scen_code, (scen_desc, sim_month) in SCENARIOS.items():
        print(f"⏳ Выполняется Сценарий {scen_code}... [{scen_desc}]")

        # А. Генерация отсутствий на год
        abs_gen.clear_absences()
        abs_gen.generate(year=2026, scenario_type=scen_code)
        db._load_absences()  # Перезагружаем в БД

        # Б. Симуляция (Ровно 1 месяц: Январь или Июль)
        run_simulation_sequence(
            routes_list=routes,
            db=db,
            start_month=sim_month,
            start_year=2026,
            duration=1,
            mode=config.SIMULATION_MODE
        )

        # В. Подсчет фактических уникальных водителей, вышедших на линию
        count = count_drivers_in_results(sim_month, 2026, config.SIMULATION_MODE)
        results[scen_code] = count
        print(f"   ✅ Завершено. Потребовалось водителей: {count}")

    total_time = (time.time() - start_time_global) / 60

    # ВЫВОД ФИНАЛЬНЫХ 5 ЧИСЕЛ
    print("\n" + "=" * 75)
    print("🏆 ИТОГОВЫЕ РЕЗУЛЬТАТЫ ЭКСПЕРИМЕНТА (1 МЕСЯЦ):")
    print("=" * 75)
    for scen_code, (scen_desc, _) in SCENARIOS.items():
        print(f"{scen_code}. {scen_desc:<55} | {results[scen_code]} чел.")
    print("=" * 75)
    print(f"⏱ Время выполнения: {total_time:.1f} мин.")


if __name__ == "__main__":
    run_experiments()