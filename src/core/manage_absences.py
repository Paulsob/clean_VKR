import sys
import os
import json
import random
import logging
from datetime import datetime, timedelta

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.logger import get_logger, get_file_only_logger
    from src.prepare_data.database import DataLoader
    import src.config as config
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    sys.exit(1)

logger = get_file_only_logger("absences_manager")
ABSENCES_FILE = os.path.join(project_root, "data", "absences.json")


def load_absences():
    if not os.path.exists(ABSENCES_FILE):
        return {"absences": []}
    try:
        with open(ABSENCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"absences": []}


def save_absences(data):
    os.makedirs(os.path.dirname(ABSENCES_FILE), exist_ok=True)
    with open(ABSENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.debug(f"Сохранено {len(data.get('absences', []))} записей")


def validate_date(date_text):
    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d")
        return dt
    except ValueError:
        return None


def check_overlap(start1, end1, start2, end2):
    return max(start1, start2) <= min(end1, end2)


def get_type_name(t_code):
    if t_code == "sick": return "Больничный"
    if t_code == "vacation": return "Отпуск"
    if t_code == "other": return "Прочее"
    return t_code


def show_all():
    data = load_absences()
    print("\n=== ТЕКУЩИЕ ОТСУТСТВИЯ ===")
    if not data["absences"]:
        print("Список пуст.")
        return

    # Сортировка: сначала реальные, потом из симуляции
    sorted_absences = sorted(data["absences"],
                             key=lambda x: (x.get('comment', '').find('[SIMULATION]') != -1, x['from']))

    print(f"{'№':<3} | {'Таб.№':<7} | {'Тип':<10} | {'Период':<23} | {'Комментарий'}")
    print("-" * 90)

    for i, item in enumerate(sorted_absences, 1):
        t = get_type_name(item["type"])
        period = f"{item['from']} - {item['to']}"
        comment = item.get('comment', '')
        print(f"{i:<3} | {item['driver_id']:<7} | {t:<10} | {period:<23} | {comment}")


def add_absence():
    print("\nДОБАВЛЕНИЕ (РУЧНОЕ)")
    driver_id = input("Табельный номер водителя: ").strip()

    print("Тип: 1 - Больничный, 2 - Отпуск, 3 - Прочее")
    t = input("Выбор: ").strip()

    if t == "1":
        absence_type = "sick"
    elif t == "2":
        absence_type = "vacation"
    elif t == "3":
        absence_type = "other"
    else:
        print("Ошибка выбора.")
        return

    date_from_str = input("Дата начала (ГГГГ-ММ-ДД): ").strip()
    date_to_str = input("Дата окончания (ГГГГ-ММ-ДД): ").strip()
    comment = input("Комментарий: ").strip()

    dt_from = validate_date(date_from_str)
    dt_to = validate_date(date_to_str)

    if not dt_from or not dt_to or dt_to < dt_from:
        print("Ошибка в датах.")
        return

    data = load_absences()
    for item in data["absences"]:
        if item["driver_id"] == driver_id:
            exist_start = validate_date(item["from"])
            exist_end = validate_date(item["to"])
            if check_overlap(dt_from, dt_to, exist_start, exist_end):
                print(f"Пересечение: {item['type']} ({item['from']} - {item['to']})")
                if input("Добавить всё равно? (да/нет): ").lower() != "да":
                    return

    data["absences"].append({
        "driver_id": driver_id,
        "type": absence_type,
        "from": date_from_str,
        "to": date_to_str,
        "comment": comment
    })
    save_absences(data)
    print("Запись добавлена.")


def extend_sick_leave():
    print("\nПРОДЛЕНИЕ БОЛЬНИЧНОГО")
    driver_id = input("Табельный номер водителя: ").strip()
    data = load_absences()

    user_leaves = [
        (i, x) for i, x in enumerate(data["absences"])
        if x["driver_id"] == driver_id and x["type"] == "sick"
    ]

    if not user_leaves:
        print("Активных больничных не найдено.")
        return

    user_leaves.sort(key=lambda x: x[1]['to'])
    idx, item = user_leaves[-1]

    print(f"Текущий больничный: до {item['to']}")
    new_date = input("Продлить ДО (ГГГГ-ММ-ДД): ").strip()
    new_dt = validate_date(new_date)
    current_end = validate_date(item['to'])

    if not new_dt or new_dt <= current_end:
        print("Новая дата должна быть больше текущей.")
        return

    data["absences"][idx]["to"] = new_date
    data["absences"][idx]["comment"] = (item.get("comment", "") + " (Продлен)").strip()
    save_absences(data)
    print("Больничный продлен.")


def remove_absence():
    show_all()
    data = load_absences()
    if not data["absences"]: return

    sorted_absences = sorted(data["absences"],
                             key=lambda x: (x.get('comment', '').find('[SIMULATION]') != -1, x['from']))

    try:
        num = int(input("\nВведите номер для удаления: ")) - 1
        if 0 <= num < len(sorted_absences):
            to_remove = sorted_absences[num]
            data["absences"].remove(to_remove)
            save_absences(data)
            print("Удалено.")
        else:
            print("Неверный номер.")
    except ValueError:
        print("Нужно ввести число.")


def clear_simulation_only():
    data = load_absences()
    original_count = len(data["absences"])
    data["absences"] = [x for x in data["absences"] if "[SIMULATION]" not in x.get("comment", "")]

    removed = original_count - len(data["absences"])
    if removed > 0:
        save_absences(data)
        print(f"Удалено {removed} записей моделирования.")
    else:
        print("Записей моделирования не найдено.")


def clear_all():
    if input("Удалить АБСОЛЮТНО ВСЕ записи? (да/нет): ").lower() == "да":
        save_absences({"absences": []})
        print("База очищена.")


def generate_random_absences():
    print("\nГЕНЕРАТОР ОТСУТСТВИЙ (МОДЕЛИРОВАНИЕ)")

    logging.getLogger("src.database").setLevel(logging.WARNING)
    logging.getLogger("database").setLevel(logging.WARNING)

    print("Загружаю список водителей...")

    loader = DataLoader(data_folder=os.path.join(project_root, "data"))
    loader.load_all()

    all_drivers = loader.drivers

    current_month = config.SELECTED_MONTH
    month_drivers = [d for d in all_drivers if d.month == current_month]

    if not month_drivers:
        print(f"В базе нет водителей за месяц {current_month} (или проверьте config.py).")
        return

    candidates = []
    if getattr(config, "PROCESS_ALL_ROUTES", True):
        print(f"Режим: Все маршруты ({len(month_drivers)} водителей доступно)")
        candidates = month_drivers
    else:
        target_route = str(getattr(config, "SELECTED_ROUTE", "1"))
        print(f"Режим: Только маршрут {target_route}")
        candidates = [d for d in month_drivers if str(d.assigned_route_number) == target_route]
        print(f"   Найдено {len(candidates)} водителей на маршруте.")

    if not candidates:
        print("Нет водителей для выбора.")
        return

    # Ввод данных
    start_date_str = input("\nДата начала (ГГГГ-ММ-ДД): ").strip()
    dt_start = validate_date(start_date_str)
    if not dt_start:
        print("Неверная дата.")
        return

    try:
        duration = int(input("Длительность (дней): ").strip())
        dt_end = dt_start + timedelta(days=duration - 1)
        end_date_str = dt_end.strftime("%Y-%m-%d")
    except ValueError:
        print("Длительность должна быть числом.")
        return

    print(f"Период: {start_date_str} - {end_date_str}")

    try:
        count_sick = int(input("Кол-во больничных: "))
        count_vac = int(input("Кол-во отпусков: "))
        count_other = int(input("Кол-во прочих: "))
    except ValueError:
        print("Вводите только числа.")
        return

    total_needed = count_sick + count_vac + count_other
    if total_needed == 0:
        print("Выбрано 0 человек.")
        return

    data = load_absences()
    existing_absences = data["absences"]
    available_drivers = []

    print("Проверка занятости...")
    for driver in candidates:
        is_busy = False
        for rec in existing_absences:
            if str(rec["driver_id"]) == str(driver.id):
                rec_start = validate_date(rec["from"])
                rec_end = validate_date(rec["to"])
                if check_overlap(dt_start, dt_end, rec_start, rec_end):
                    is_busy = True
                    break
        if not is_busy:
            available_drivers.append(driver)

    if len(available_drivers) < total_needed:
        print(f"Недостаточно свободных водителей! (Нужно {total_needed}, доступно {len(available_drivers)})")
        if input("Заполнить теми, кто есть? (да/нет): ").lower() != "да":
            return
        total_needed = len(available_drivers)

    random.shuffle(available_drivers)

    selected_sick = available_drivers[:count_sick]
    rem = available_drivers[count_sick:]

    selected_vac = rem[:count_vac]
    rem = rem[count_vac:]

    selected_other = rem[:count_other]

    def make_entry(d, t):
        return {
            "driver_id": str(d.id),
            "type": t,
            "from": start_date_str,
            "to": end_date_str,
            "comment": "[SIMULATION] Автогенерация"
        }

    new_entries = []
    new_entries.extend([make_entry(d, "sick") for d in selected_sick])
    new_entries.extend([make_entry(d, "vacation") for d in selected_vac])
    new_entries.extend([make_entry(d, "other") for d in selected_other])

    data["absences"].extend(new_entries)
    save_absences(data)

    print(f"\nДобавлено {len(new_entries)} записей.")
    print("Используйте пункт 6 меню, чтобы удалить их.")


def main():
    while True:
        print("\nУПРАВЛЕНИЕ ОТСУТСТВИЯМИ")
        print("1. Показать все")
        print("2. Добавить реальные данные отсутствия")
        print("3. Продлить больничный")
        print("4. Удалить одну запись")
        print("5. Добавить данные для моделирования")
        print("6. Удалить данные для моделирования")
        print("7. Удалить все записи")
        print("0. Выход")

        choice = input("Выбор: ").strip()

        if choice == "1":
            show_all()
        elif choice == "2":
            add_absence()
        elif choice == "3":
            extend_sick_leave()
        elif choice == "4":
            remove_absence()
        elif choice == "5":
            generate_random_absences()
        elif choice == "6":
            clear_simulation_only()
        elif choice == "7":
            clear_all()
        elif choice == "0":
            break
        else:
            print("Неверный выбор.")


if __name__ == "__main__":
    main()
