import sys
import os
import json
from datetime import datetime

# Пути
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
os.chdir(project_root)

ABSENCES_FILE = "data/absences.json"


def load_absences():
    if not os.path.exists(ABSENCES_FILE):
        return {"absences": []}
    with open(ABSENCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_absences(data):
    os.makedirs(os.path.dirname(ABSENCES_FILE), exist_ok=True)
    with open(ABSENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def show_all():
    data = load_absences()
    print("\n=== ТЕКУЩИЕ ОТСУТСТВИЯ ===")
    if not data["absences"]:
        print("Список пуст.")
        return
    for i, item in enumerate(data["absences"], 1):
        t = "Больничный" if item["type"] == "sick" else "Отпуск"
        print(f"{i}. Таб.№{item['driver_id']} | {t} | {item['from']} - {item['to']} | {item.get('comment', '')}")


def add_absence():
    print("\n--- ДОБАВЛЕНИЕ ОТСУТСТВИЯ ---")
    driver_id = input("Табельный номер водителя: ").strip()

    print("Тип: 1 - Больничный, 2 - Отпуск")
    t = input("Выбор (1/2): ").strip()
    absence_type = "sick" if t == "1" else "vacation"

    date_from = input("Дата начала (ГГГГ-ММ-ДД): ").strip()
    date_to = input("Дата окончания (ГГГГ-ММ-ДД): ").strip()
    comment = input("Комментарий (необязательно): ").strip()

    # Валидация дат
    try:
        datetime.strptime(date_from, "%Y-%m-%d")
        datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        print("Неверный формат даты!")
        return

    data = load_absences()
    data["absences"].append({
        "driver_id": driver_id,
        "type": absence_type,
        "from": date_from,
        "to": date_to,
        "comment": comment
    })
    save_absences(data)
    print("✅ Запись добавлена.")


def remove_absence():
    data = load_absences()
    show_all()
    if not data["absences"]:
        return

    try:
        idx = int(input("\nНомер записи для удаления: ")) - 1
        if 0 <= idx < len(data["absences"]):
            removed = data["absences"].pop(idx)
            save_absences(data)
            print(f"✅ Удалено: {removed['driver_id']}")
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
        print("3. Удалить запись")
        print("4. Очистить все")
        print("0. Выход")

        choice = input("Выбор: ").strip()

        if choice == "1":
            show_all()
        elif choice == "2":
            add_absence()
        elif choice == "3":
            remove_absence()
        elif choice == "4":
            clear_all()
        elif choice == "0":
            break
        else:
            print("Неверный выбор.")


if __name__ == "__main__":
    main()