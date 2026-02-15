import sys
import os
import json
import calendar
from datetime import date

# Настройка путей
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
os.chdir(project_root)

from src.prepare_data.database import DataLoader
from src.core.scheduler import WorkforceAnalyzer

# ================= НАСТРОЙКИ =================
TARGET_YEAR = 2025
TARGET_MONTH_NAME = "Декабрь"
START_DAY = 24
END_DAY = 31
HISTORY_DIR = "history/12_Декабрь_2025"


# =============================================

def main():
    print(f"--- ГЕНЕРАЦИЯ ИСТОРИИ: {TARGET_MONTH_NAME} {TARGET_YEAR} ---")

    # 1. Загрузка данных
    db = DataLoader()
    db.load_all()

    # 2. Получаем список всех уникальных маршрутов из расписания
    all_routes = sorted(list(set(str(s.route_number) for s in db.schedules)))
    print(f"Найдено маршрутов: {len(all_routes)}")

    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)

    # 3. Цикл по каждому маршруту
    for route in all_routes:
        print(f"Обработка маршрута {route}...", end=" ")

        # Создаем анализатор для конкретного маршрута
        analyzer = WorkforceAnalyzer(db)

        # Проходим по дням с 24 по 31 декабря
        for day in range(START_DAY, END_DAY + 1):
            # Симулируем распределение.
            # Результат функции нам не важен, так как нам нужна только заполненная история внутри analyzer
            analyzer.generate_daily_roster(
                route_number=route,
                day_of_month=day,
                target_month=TARGET_MONTH_NAME,
                target_year=TARGET_YEAR,
                mode="real"  # Используем real, чтобы не блокировать при мелких недоотдыхах
            )

        # 4. Получаем историю в сериализуемом формате
        history_data = analyzer.get_history_serializable()

        # Если водители распределялись, сохраняем файл
        if history_data:
            file_name = f"history_{route}_{TARGET_MONTH_NAME}_{TARGET_YEAR}.json"
            file_path = os.path.join(HISTORY_DIR, file_name)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            print(f"OK (сохранено {len(history_data)} записей)")
        else:
            print("Пропуск (нет задействованных водителей)")

    print(f"\n✅ Все файлы истории сохранены в папку: {HISTORY_DIR}")


if __name__ == "__main__":
    main()