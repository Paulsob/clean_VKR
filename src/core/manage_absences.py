import sys
import os
import json
from datetime import datetime

# Пути (используем абсолютные пути, не меняя рабочую директорию)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from src.logger import get_logger, get_file_only_logger

# Инициализируем логгер только для файлов (не выводит в консоль)
logger = get_file_only_logger(__name__)

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
    logger.debug(f"Сохранено {len(data.get('absences', []))} записей об отсутствиях")


def show_all():
    data = load_absences()
    print("\n=== ТЕКУЩИЕ ОТСУТСТВИЯ ===")
    if not data["absences"]:
        print("Список пуст.")
        return
    # Сортируем для удобства (сначала новые)
    sorted_absences = sorted(data["absences"], key=lambda x: x['from'])

    for i, item in enumerate(sorted_absences, 1):
        t = "Больничный" if item["type"] == "sick" else "Отпуск"
        # Для удобства показываем оригинальный индекс, чтобы можно было удалить
        print(f"{i}. Таб.№{item['driver_id']} | {t} | {item['from']} - {item['to']} | {item.get('comment', '')}")
    
    # Этот лог пойдет только в файл, не в консоль
    logger.info(f"Показано {len(data['absences'])} записей об отсутствиях")


def validate_date(date_text):
    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d")
        return dt
    except ValueError:
        return None


def check_overlap(start1, end1, start2, end2):
    """
    Возвращает True, если интервалы пересекаются.
    start1, end1, start2, end2 - объекты datetime
    """
    return max(start1, start2) <= min(end1, end2)


def add_absence():
    print("\n--- ДОБАВЛЕНИЕ ОТСУТСТВИЯ ---")
    driver_id = input("Табельный номер водителя: ").strip()

    print("Тип: 1 - Больничный, 2 - Отпуск")
    t = input("Выбор (1/2): ").strip()
    if t not in ["1", "2"]:
        print("Ошибка выбора.")
        return
    absence_type = "sick" if t == "1" else "vacation"

    date_from_str = input("Дата начала (ГГГГ-ММ-ДД): ").strip()
    date_to_str = input("Дата окончания (ГГГГ-ММ-ДД): ").strip()
    comment = input("Комментарий (необязательно): ").strip()

    dt_from = validate_date(date_from_str)
    dt_to = validate_date(date_to_str)

    if not dt_from or not dt_to:
        print("❌ Ошибка: Неверный формат даты.")
        return

    if dt_to < dt_from:
        print("❌ Ошибка: Дата окончания раньше начала.")
        return

    data = load_absences()

    # --- ЛОГИКА ПРОВЕРКИ ПЕРЕСЕЧЕНИЙ ---
    conflict_found = False

    # Проходимся по существующим записям этого водителя
    for idx, item in enumerate(data["absences"]):
        if item["driver_id"] != driver_id:
            continue

        existing_start = validate_date(item["from"])
        existing_end = validate_date(item["to"])

        # Проверяем пересечение
        if check_overlap(dt_from, dt_to, existing_start, existing_end):

            # СЦЕНАРИЙ 1: Больничный накладывается на Больничный
            if absence_type == "sick" and item["type"] == "sick":
                print(f"\n⚠️  ВНИМАНИЕ: У водителя {driver_id} уже есть больничный:")
                print(f"   С {item['from']} по {item['to']}")

                # Если новый больничный полностью внутри старого - ничего делать не надо
                if dt_from >= existing_start and dt_to <= existing_end:
                    print("   Новый период полностью входит в существующий. Добавление не требуется.")
                    return

                # Предлагаем продлить
                user_choice = input(
                    "   Хотите ПРОДЛИТЬ существующий больничный до новой даты? (да/нет): ").lower().strip()
                if user_choice == "да":
                    # Вычисляем новый конец (максимум из старого и нового)
                    new_end_dt = max(existing_end, dt_to)
                    data["absences"][idx]["to"] = new_end_dt.strftime("%Y-%m-%d")

                    # Обновляем коммент
                    if comment:
                        data["absences"][idx]["comment"] = (
                                    data["absences"][idx].get("comment", "") + " " + comment).strip()

                    save_absences(data)
                    logger.info(f"Больничный водителя {driver_id} обновлен до {data['absences'][idx]['to']}")
                    print(f"✅ Больничный обновлен. Новый срок: до {data['absences'][idx]['to']}")
                    return
                else:
                    print("   Создаю отдельную запись (наложение дат!).")

            # СЦЕНАРИЙ 2: Наложение на Отпуск (или наоборот)
            elif absence_type != item["type"]:
                r_type = "Отпуск" if item["type"] == "vacation" else "Больничный"
                print(f"\n⚠️  ПРЕДУПРЕЖДЕНИЕ: Пересечение с записью '{r_type}' ({item['from']} - {item['to']}).")
                confirm = input("   Всё равно добавить запись? (да/нет): ").lower().strip()
                if confirm != "да":
                    print("   Отмена добавления.")
                    return

    # Если мы здесь, значит либо конфликтов нет, либо пользователь настоял на создании новой записи
    data["absences"].append({
        "driver_id": driver_id,
        "type": absence_type,
        "from": date_from_str,
        "to": date_to_str,
        "comment": comment
    })
    save_absences(data)
    logger.info(f"Добавлено отсутствие: водитель {driver_id}, тип {absence_type}, период {date_from_str} - {date_to_str}")
    print("✅ Запись добавлена.")


def extend_sick_leave():
    """
    Продлевает последний активный больничный для указанного водителя.
    """
    print("\n--- ПРОДЛЕНИЕ БОЛЬНИЧНОГО ---")
    driver_id = input("Табельный номер водителя: ").strip()

    data = load_absences()

    # Ищем все больничные этого водителя
    driver_sick_leaves = []
    for idx, item in enumerate(data["absences"]):
        if item["driver_id"] == driver_id and item["type"] == "sick":
            driver_sick_leaves.append((idx, item))

    if not driver_sick_leaves:
        print(f"❌ У водителя {driver_id} нет записей о больничных.")
        return

    # Находим самый поздний больничный (по дате окончания)
    # Сортируем по дате 'to'
    driver_sick_leaves.sort(key=lambda x: datetime.strptime(x[1]["to"], "%Y-%m-%d"))

    last_idx, last_sick = driver_sick_leaves[-1]

    print(f"Найден последний больничный: с {last_sick['from']} по {last_sick['to']}")

    new_date_str = input("Продлить ДО (ГГГГ-ММ-ДД): ").strip()
    new_dt = validate_date(new_date_str)

    if not new_dt:
        print("❌ Неверный формат даты.")
        return

    current_end_dt = datetime.strptime(last_sick["to"], "%Y-%m-%d")

    if new_dt <= current_end_dt:
        print("❌ Ошибка: Новая дата должна быть позже текущей даты окончания.")
        return

    # Обновляем запись
    data["absences"][last_idx]["to"] = new_date_str

    # Можно дописать комментарий о продлении
    old_comment = data["absences"][last_idx].get("comment", "")
    data["absences"][last_idx]["comment"] = f"{old_comment} (Продлен до {new_date_str})".strip()

    save_absences(data)
    logger.info(f"Больничный водителя {driver_id} продлен до {new_date_str}")
    print(f"✅ Больничный водителя {driver_id} продлен до {new_date_str}.")
    print("ℹ️  Не забудьте запустить run_simulation для перераспределения смен!")


def remove_absence():
    data = load_absences()
    # Лучше показывать с индексами массива, чтобы удалять точно
    print("\nВыберите номер записи для удаления:")
    if not data["absences"]:
        print("Список пуст.")
        return

    for i, item in enumerate(data["absences"], 1):
        print(f"{i}. [{item['driver_id']}] {item['type']} {item['from']} -> {item['to']}")

    try:
        choice = input("Номер: ").strip()
        idx = int(choice) - 1
        if 0 <= idx < len(data["absences"]):
            removed = data["absences"].pop(idx)
            save_absences(data)
            logger.info(f"Удалена запись об отсутствии: {removed['driver_id']} ({removed['from']}-{removed['to']})")
            print(f"✅ Удалено: {removed['driver_id']} ({removed['from']}-{removed['to']})")
        else:
            print("Неверный номер.")
    except ValueError:
        print("Введите число.")


def clear_all():
    confirm = input("Удалить ВСЕ записи? (да/нет): ").strip().lower()
    if confirm == "да":
        save_absences({"absences": []})
        print("✅ Все записи удалены.")


def main():
    while True:
        print("\n=== УПРАВЛЕНИЕ ОТСУТСТВИЯМИ ===")
        print("1. Показать все")
        print("2. Добавить больничный/отпуск")
        print("3. Продлить больничный")  # Новая команда
        print("4. Удалить запись")
        print("5. Очистить все")
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
            clear_all()
        elif choice == "0":
            break
        else:
            print("Неверный выбор.")


if __name__ == "__main__":
    main()