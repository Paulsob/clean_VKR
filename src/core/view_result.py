import json
import os
import sys

# === НАСТРОЙКИ ===
ROUTE = "9"
MONTH = "Февраль"
YEAR = 2026
# Путь с учетом вашей структуры папок
INPUT_FILE = f"data/results/simulation_{ROUTE}_{MONTH}_{YEAR}.json"


def get_driver_name(tram_data, shift_num):
    """
    Универсальная функция для получения водителя.
    Поддерживает и старую структуру (shift_1_driver), и новую (shift_1 -> driver).
    """
    # 1. Пробуем старый формат (плоский)
    key_flat = f"shift_{shift_num}_driver"
    if key_flat in tram_data:
        return tram_data[key_flat]

    # 2. Пробуем новый формат (вложенный)
    key_nested = f"shift_{shift_num}"
    if key_nested in tram_data and isinstance(tram_data[key_nested], dict):
        return tram_data[key_nested].get("driver")

    return None


def main():
    # Проверка наличия файла
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Файл {INPUT_FILE} не найден.")
        print(f"Убедитесь, что вы запустили run_month.py и путь к файлу верный.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"--- ПРОСМОТР РЕЗУЛЬТАТОВ: {MONTH} {YEAR} ---")
    print(f"Всего дней в файле: {len(data)}")

    while True:
        print("\nВведите день для просмотра (или 'q' для выхода):")
        user_input = input("> ").strip()

        if user_input.lower() == 'q':
            break

        if user_input not in data:
            print(f"❌ Нет данных за день '{user_input}'. Доступные дни: {list(data.keys())[:5]}...")
            continue

        result = data[user_input]

        # Проверка на ошибки генерации
        if "error" in result:
            print(f"⛔ ОШИБКА В РАСЧЕТЕ ДНЯ: {result['error']}")
            continue

        # === ВЫВОД ===
        print("\n" + "=" * 60)
        route_num = result.get('route', 'Unknown')
        print(f"📄 РЕЗУЛЬТАТ: Маршрут №{route_num}")
        print(f"📅 Дата: {user_input} {MONTH} {YEAR}")

        # Доп. инфо, если есть
        if 'day_name' in result:
            print(f"🗓  День: {result['day_name']} ({result.get('day_type', '')})")
        print("=" * 60 + "\n")

        roster = result.get("roster", [])
        if not roster:
            print("⚠️ Список нарядов пуст.")

        for tram in roster:
            # Используем универсальную функцию
            u_driver = get_driver_name(tram, 1) or '❌ ПУСТО'
            v_driver = get_driver_name(tram, 2) or '❌ ПУСТО'

            t_num = tram.get('tram_number', '???')
            print(f"Вагон {t_num}:")
            print(f"  🌞 Утро : {u_driver}")
            print(f"  🌜 Вечер: {v_driver}")

            # Вывод проблем (issues)
            issues = tram.get('issues', [])
            if issues:
                for issue in issues:
                    print(f"     ⚠️ {issue}")

            # Вывод предупреждений (warnings из новой структуры), если они есть
            if 'shift_1' in tram and isinstance(tram['shift_1'], dict):
                warns = tram['shift_1'].get('warnings', [])
                for w in warns: print(f"     ⚠️ (Утро) {w}")

            if 'shift_2' in tram and isinstance(tram['shift_2'], dict):
                warns = tram['shift_2'].get('warnings', [])
                for w in warns: print(f"     ⚠️ (Вечер) {w}")

        print("-" * 30)
        # Статистика резерва (поддержка разных ключей)
        if 'drivers_leftover' in result:
            leftover = result['drivers_leftover']
            print(f"Резерв: {len(leftover)} чел.")
        elif 'stats' in result and 'leftover' in result['stats']:
            print(f"Резерв: {result['stats']['leftover']} чел.")


if __name__ == "__main__":
    main()