import json
import os
import calendar
# ВАЖНО: Проверь этот импорт. Он должен указывать туда, где лежит твой class DataLoader
from src.database import DataLoader
# ВАЖНО: Проверь этот импорт. Он должен указывать туда, где лежит твой class WorkforceAnalyzer
from src.scheduler import WorkforceAnalyzer

# === НАСТРОЙКИ ===
ROUTE = "47"
MONTH = "Февраль"
YEAR = 2026
OUTPUT_FILE = f"data/results/simulation_{ROUTE}_{MONTH}_{YEAR}.json"


def main():
    print(f"--- ЗАПУСК МОДЕЛИРОВАНИЯ: {MONTH} {YEAR}, Маршрут {ROUTE} ---")

    # 1. Загрузка данных
    try:
        db = DataLoader()
        db.load_all()
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
        return

    analyzer = WorkforceAnalyzer(db)

    # Карта месяцев
    month_map = {
        "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6,
        "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12
    }
    month_num = month_map.get(MONTH, 2)
    _, days_in_month = calendar.monthrange(YEAR, month_num)

    full_month_results = {}

    # 2. Цикл по дням
    for day in range(1, days_in_month + 1):
        print(f"Расчет дня: {day}/{days_in_month}...", end="\r")

        try:
            day_result = analyzer.generate_daily_roster(
                route_number=ROUTE,
                day_of_month=day,
                target_month=MONTH,
                target_year=YEAR
            )
            full_month_results[str(day)] = day_result
        except Exception as e:
            print(f"\n❌ Ошибка при расчете дня {day}: {e}")
            full_month_results[str(day)] = {"error": str(e)}

    print(f"\n✅ Готово! Расчет завершен.")

    # 3. Сохранение
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        # default=str нужен, чтобы даты/время превратились в строки, если они есть
        json.dump(full_month_results, f, ensure_ascii=False, indent=2, default=str)

    print(f"Результаты сохранены: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()