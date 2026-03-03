import json
import os
import sys

# Добавляем корень проекта
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import src.config as config


def get_pattern_name(driver_id):
    """Определяет график по ID"""
    try:
        did = int(driver_id)
        if did < 10000:
            return "4x2"
        elif 10000 <= did < 20000:
            return "5x2"
        elif 20000 <= did < 30000:
            return "5x2_holiday"
        else:
            return "Unknown"
    except:
        return "Error"


def analyze_results():
    results_dir = config.RESULTS_DIR
    target_mode = config.SIMULATION_MODE  # Берем режим из конфига ("real" или "strict")

    print(f"\n📊 АНАЛИЗ РЕЗУЛЬТАТОВ")
    print(f"📁 Папка: {results_dir}")
    print(f"⚙️  Режим фильтрации: {target_mode}")

    if not os.path.exists(results_dir):
        print("❌ Папка не найдена.")
        return

    stats = {}
    files_processed = 0

    # Проходим по всем файлам
    for root, dirs, files in os.walk(results_dir):
        for file in files:
            # ФИЛЬТР: Читаем только файлы выбранного режима
            # Имя файла: simulation_real_47_Jan_2026.json
            if not file.startswith(f"simulation_{target_mode}_"):
                continue

            files_processed += 1
            full_path = os.path.join(root, file)

            with open(full_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

                for day_key, day_data in data.items():
                    roster = day_data.get('roster', [])
                    for tram in roster:
                        for shift in ['shift_1', 'shift_2']:
                            info = tram.get(shift)
                            if info:
                                d_id = str(info['driver'])
                                hours = float(info['work_hours'])

                                if d_id not in stats:
                                    stats[d_id] = {
                                        'hours': 0.0,
                                        'shifts': 0,
                                        'pattern': get_pattern_name(d_id)
                                    }

                                stats[d_id]['hours'] += hours
                                stats[d_id]['shifts'] += 1

    print(f"📄 Обработано файлов: {files_processed}")

    if files_processed == 0:
        print("⚠️ Файлов не найдено! Проверьте, запускали ли вы симуляцию в этом режиме.")
        return

    print("-" * 75)
    print(f"{'ГРАФИК':<12} | {'ID':<10} | {'СМЕНЫ':<6} | {'ЧАСЫ':<8} | {'СТАТУС'}")
    print("-" * 75)

    # Сортируем: сначала по ГРАФИКУ, потом по ЧАСАМ (по убыванию)
    sorted_drivers = sorted(stats.items(), key=lambda x: (x[1]['pattern'], x[1]['hours']), reverse=True)

    pattern_summary = {}

    for d_id, data in sorted_drivers:
        pat = data['pattern']
        h = data['hours']
        pattern_summary[pat] = pattern_summary.get(pat, 0) + h

        # Маркер для мало работающих
        status = ""
        if h < 100: status = "⚠️ МАЛО"
        if h > 180: status = "🔥 МНОГО"

        # Выводим (сократим список, если очень много, но "мало работающих" покажем всех)
        if len(sorted_drivers) < 60 or h < 40 or h > 160:
            print(f"{pat:<12} | {d_id:<10} | {data['shifts']:<6} | {h:<8.1f} | {status}")

    print("-" * 75)
    print("ИТОГИ ПО ТИПАМ ГРАФИКОВ (Человеко-часы):")
    for p, val in pattern_summary.items():
        print(f"🔹 {p}: {val:.1f} ч")


if __name__ == "__main__":
    analyze_results()