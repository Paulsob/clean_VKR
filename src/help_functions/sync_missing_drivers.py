import json
import os

# НАСТРОЙКИ ПУТЕЙ
DRIVERS_PATH = "../../data/drivers_json/drivers_april.json"
ASSIGNMENTS_PATH = "../../data/assignments.json"


def sync_drivers():
    # 1. ПРОВЕРКА ФАЙЛОВ
    if not os.path.exists(DRIVERS_PATH):
        print(f"❌ Файл водителей не найден: {DRIVERS_PATH}")
        return
    if not os.path.exists(ASSIGNMENTS_PATH):
        print(f"❌ Файл закреплений не найден: {ASSIGNMENTS_PATH}")
        return

    print(f"📖 Читаю водителей из: {DRIVERS_PATH}...")

    # 2. СБОР ID ВОДИТЕЛЕЙ ИЗ ТАБЕЛЯ
    drivers_ids = set()
    try:
        with open(DRIVERS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Проверяем структуру (месяц это или список)
            if isinstance(data, dict) and "drivers" in data:
                drivers_list = data["drivers"]
            elif isinstance(data, list):
                drivers_list = data
            else:
                print("❌ Непонятная структура файла водителей")
                return

            for d in drivers_list:
                # Приводим к int, чтобы "009" и 9 считались одним и тем же
                try:
                    uid = int(d.get("tab_number"))
                    drivers_ids.add(uid)
                except (ValueError, TypeError):
                    continue

    except Exception as e:
        print(f"❌ Ошибка чтения водителей: {e}")
        return

    print(f"   Найдено {len(drivers_ids)} водителей в табеле.")

    # 3. СБОР ID ИЗ ЗАКРЕПЛЕНИЙ
    print(f"📖 Читаю текущие закрепления: {ASSIGNMENTS_PATH}...")
    assigned_ids = set()
    current_assignments = []

    try:
        with open(ASSIGNMENTS_PATH, "r", encoding="utf-8") as f:
            current_assignments = json.load(f)
            for a in current_assignments:
                try:
                    uid = int(a.get("driver_id"))
                    assigned_ids.add(uid)
                except (ValueError, TypeError):
                    continue
    except Exception as e:
        print(f"❌ Ошибка чтения закреплений: {e}")
        return

    print(f"   Найдено {len(assigned_ids)} уже закрепленных водителей.")

    # 4. ПОИСК ПОТЕРЯШЕК
    # Вычитаем множества: (Все водители) - (Закрепленные)
    missing_ids = drivers_ids - assigned_ids

    if not missing_ids:
        print("\n✅ Все водители уже закреплены! Добавлять некого.")
        return

    print(f"\n🔍 Обнаружено {len(missing_ids)} незакрепленных водителей.")
    print("   Добавляю их в маршрут 'ANY'...")

    # 5. ДОБАВЛЕНИЕ
    new_entries = []
    for missing_id in missing_ids:
        new_entry = {
            "driver_id": missing_id,
            "route_number": "ANY"
        }
        current_assignments.append(new_entry)
        new_entries.append(missing_id)

    # 6. СОХРАНЕНИЕ
    try:
        with open(ASSIGNMENTS_PATH, "w", encoding="utf-8") as f:
            json.dump(current_assignments, f, ensure_ascii=False, indent=2)
        print("💾 Файл assignments.json успешно обновлен!")

        # Вывод первых 5 добавленных для примера
        print(f"   Примеры добавленных ID: {list(new_entries)[:5]}...")

    except Exception as e:
        print(f"❌ Ошибка при сохранении: {e}")


if __name__ == "__main__":
    sync_drivers()