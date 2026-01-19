import pandas as pd
import json
import os

# НАСТРОЙКИ
EXCEL_PATH = "../../data/закрепления.xlsx"
JSON_PATH = "../../data/assignments.json"
RESERVE_ROUTE_NAME = "ANY"  # Как будем называть "свободных" водителей


def run_import():
    if not os.path.exists(EXCEL_PATH):
        print(f"❌ Файл {EXCEL_PATH} не найден!")
        return

    print(f"📖 Читаю Excel: {EXCEL_PATH}...")

    # Читаем Excel (берем первую колонку, независимо от заголовка)
    try:
        df = pd.read_excel(EXCEL_PATH)
        # Берем данные из самого первого столбца (индекс 0)
        id_column = df.iloc[:, 0]
    except Exception as e:
        print(f"❌ Ошибка чтения Excel: {e}")
        return

    new_entries = []

    # Пробегаем по строкам
    for raw_id in id_column:
        try:
            # Превращаем в чистое целое число (убираем .0 если есть)
            driver_id = int(raw_id)

            new_entries.append({
                "driver_id": driver_id,
                "route_number": RESERVE_ROUTE_NAME
            })
        except ValueError:
            # Если попался заголовок или пустая строка
            continue

    print(f"🔍 Найдено в Excel {len(new_entries)} водителей.")

    # --- ЗАГРУЗКА И СЛИЯНИЕ С СУЩЕСТВУЮЩИМ JSON ---
    existing_data = []
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Существующий JSON был пуст или поврежден. Создаем новый.")

    # Создаем список уже существующих ID, чтобы не дублировать
    # (Если водитель 101 уже закреплен за маршрутом 1, мы не должны добавлять его в ANY)
    existing_ids = {item["driver_id"] for item in existing_data}

    added_count = 0
    for entry in new_entries:
        if entry["driver_id"] not in existing_ids:
            existing_data.append(entry)
            added_count += 1
        else:
            # Опционально: можно написать print, если хочешь знать, кого пропустили
            pass

    # --- СОХРАНЕНИЕ ---
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Готово! Добавлено {added_count} новых водителей в группу '{RESERVE_ROUTE_NAME}'.")
    print(f"   Всего закреплений теперь: {len(existing_data)}")


if __name__ == "__main__":
    run_import()