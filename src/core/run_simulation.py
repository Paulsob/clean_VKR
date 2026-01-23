import sys
import os
import json
import calendar

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
os.chdir(project_root)

from src.config import (
    SELECTED_ROUTE, SELECTED_MONTH, SELECTED_YEAR, SIMULATION_MODE,
    SIMULATION_RESULT_FILE, HISTORY_FILE
)
from src.prepare_data.database import DataLoader
from src.core.scheduler import WorkforceAnalyzer


def main():
    print(f"--- ЗАПУСК СИМУЛЯЦИИ ---")
    print(f"Папка запуска: {os.getcwd()}")
    print(f"Конфиг: {SELECTED_ROUTE}, {SELECTED_MONTH} {SELECTED_YEAR}, Mode={SIMULATION_MODE}")

    db = DataLoader()
    db.load_all()

    analyzer = WorkforceAnalyzer(db)

    # Загружаем историю за декабрь для выбранного маршрута
    dec_history_path = f"history/december_2025/history_{SELECTED_ROUTE}_Декабрь_2025.json"
    if os.path.exists(dec_history_path):
        with open(dec_history_path, "r", encoding="utf-8") as f:
            dec_data = json.load(f)
            analyzer.load_history(dec_data)
            print(f"Загружена история за декабрь: {len(dec_data)} водителей.")
    else:
        print("Предупреждение: Файл истории декабря не найден. Отдых в начале января будет >48.")

    # Карту месяцев можно вынести в utils, но пока пусть будет здесь
    month_map = {"Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4,
                 "Май": 5, "Июнь": 6, "Июль": 7, "Август": 8,
                 "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12}

    _, days_in_month = calendar.monthrange(SELECTED_YEAR, month_map.get(SELECTED_MONTH, 2))

    full_results = {}

    print("Расчет дней:", end=" ")
    for day in range(1, days_in_month + 1):
        print(f".", end="", flush=True)
        res = analyzer.generate_daily_roster(
            SELECTED_ROUTE, day, SELECTED_MONTH, SELECTED_YEAR, mode=SIMULATION_MODE
        )
        full_results[str(day)] = res
    print("\nГотово.")

    # Сохранение результатов
    os.makedirs(os.path.dirname(SIMULATION_RESULT_FILE), exist_ok=True)
    with open(SIMULATION_RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(full_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"Результаты: {SIMULATION_RESULT_FILE}")

    # Сохранение истории
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(analyzer.get_history_serializable(), f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
