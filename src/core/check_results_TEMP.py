import json
import os
import sys
import glob

# Добавляем корень проекта
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import src.config as config
from src.constants import get_month_number


def get_pattern_name(driver_id):
    """Определяет график по ID"""
    clean_id = str(driver_id).split()[0]
    try:
        did = int(clean_id)
        if did < 10000:
            return "4x2"
        elif 10000 <= did < 20000:
            return "5x2"
        elif 20000 <= did < 30000:
            return "5x2_holiday"
        else:
            return "Unknown"
    except ValueError:
        return "Error"


def analyze_results():
    m_num = get_month_number(config.SELECTED_MONTH)
    dir_name = f"{m_num:02d}_{config.SELECTED_MONTH}_{config.SELECTED_YEAR}"
    target_dir = os.path.join(config.RESULTS_DIR, dir_name, config.SIMULATION_MODE)

    print(f"\n📊 АНАЛИЗ РЕЗУЛЬТАТОВ (БЫСТРАЯ СВОДКА)")
    print(f"📁 Папка: {target_dir}")
    print(f"⚙️  Режим: {config.SIMULATION_MODE}")
    print(f"🚌 Маршруты: {'ВСЕ' if config.PROCESS_ALL_ROUTES else config.SELECTED_ROUTE}")

    if not os.path.exists(target_dir):
        print("❌ Папка не найдена. Симуляция для этого месяца/режима не запускалась.")
        return

    search_pattern = os.path.join(target_dir,
                                  f"simulation_{config.SIMULATION_MODE}_*_{config.SELECTED_MONTH}_{config.SELECTED_YEAR}.json")
    found_files = glob.glob(search_pattern)

    stats = {}
    files_processed = 0

    for file_path in found_files:
        basename = os.path.basename(file_path)

        if not config.PROCESS_ALL_ROUTES:
            expected_prefix = f"simulation_{config.SIMULATION_MODE}_{config.SELECTED_ROUTE}_"
            if not basename.startswith(expected_prefix):
                continue

        files_processed += 1

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue

            for day_key, day_data in data.items():
                if not day_key.isdigit():
                    continue

                roster = day_data.get('roster', [])
                for tram in roster:
                    for shift in ['shift_1', 'shift_2']:
                        info = tram.get(shift)
                        if info and info.get('driver'):
                            d_id = str(info['driver']).split()[0]
                            hours = float(info.get('work_hours', 0.0))

                            if d_id not in stats:
                                stats[d_id] = {
                                    'hours': 0.0,
                                    'shifts': 0,
                                    'pattern': get_pattern_name(d_id)
                                }

                            stats[d_id]['hours'] += hours
                            stats[d_id]['shifts'] += 1

    print(f"📄 Обработано файлов маршрутов: {files_processed}")

    if files_processed == 0:
        print("⚠️ Подходящих файлов не найдено!")
        return

    print("-" * 75)
    print(f"{'ГРАФИК':<12} | {'ID':<10} | {'СМЕНЫ':<6} | {'ЧАСЫ':<8} | {'СТАТУС'}")
    print("-" * 75)

    sorted_drivers = sorted(stats.items(), key=lambda x: (x[1]['pattern'], x[1]['hours']), reverse=True)

    # Словарь для итогов (теперь считаем и часы, и количество людей)
    pattern_summary = {}

    for d_id, data in sorted_drivers:
        pat = data['pattern']
        h = data['hours']

        if pat not in pattern_summary:
            pattern_summary[pat] = {'hours': 0.0, 'count': 0}

        pattern_summary[pat]['hours'] += h
        pattern_summary[pat]['count'] += 1

        status = ""
        if h < 140:
            status = "НЕДОСТАТОЧНО ЧАСОВ"
        elif h > 180:
            status = "МНОГО ЧАСОВ"
        else:
            status = "НОРМА"

        if len(sorted_drivers) < 60 or h < 140 or h > 180:
            print(f"{pat:<12} | {d_id:<10} | {data['shifts']:<6} | {h:<8.1f} | {status}")

    total_drivers = len(stats)

    print("-" * 75)
    print(f"👥 ВСЕГО ЗАДЕЙСТВОВАНО: {total_drivers} водителей.")
    print("ИТОГИ ПО ТИПАМ ГРАФИКОВ:")
    for p, info in pattern_summary.items():
        print(f"🔹 {p:<12}: {info['count']:<3} водителей | {info['hours']:.1f} ч.")
    print("-" * 75)


if __name__ == "__main__":
    analyze_results()