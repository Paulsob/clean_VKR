import sys
import os

# 1. Определяем корневую папку проекта (поднимаемся на 2 уровня вверх от src/core)
current_dir = os.path.dirname(os.path.abspath(__file__)) # .../src/core
project_root = os.path.dirname(os.path.dirname(current_dir)) # .../clean_VKR

# 2. Добавляем корень в пути поиска модулей (чтобы работал from src...)
sys.path.insert(0, project_root)

# 3. ВАЖНО: Меняем рабочую директорию на корень проекта
# Чтобы скрипт видел папку "data", а не искал её внутри "src/core"
os.chdir(project_root)

# Теперь импорты
from src.database import DataLoader
# Используем simple, который мы создали на прошлом шаге
from src.scheduler_simple import WorkforceAnalyzer

# === НАСТРОЙКИ ===
ROUTE = "47"
MONTH = "Февраль"
YEAR = 2026
START_DAY = 1
END_DAY = 10
DRIVERS_TO_SHOW = 15  # Показываем первых 15 водителей


def main():
    print(f"=== ОТЛАДКА РАСПРЕДЕЛЕНИЯ ===")
    print(f"Маршрут: {ROUTE}")
    print(f"Период: {START_DAY}-{END_DAY} {MONTH} {YEAR}")
    print(f"Показываем первых {DRIVERS_TO_SHOW} водителей\n")

    # 1. Загрузка данных
    db = DataLoader()
    db.load_all()

    # Получаем водителей маршрута
    route_drivers = [d for d in db.drivers
                     if str(d.assigned_route_number) == str(ROUTE) and d.month == MONTH]

    # Берем для отображения только первых N
    display_drivers = route_drivers[:DRIVERS_TO_SHOW]
    display_ids = [str(d.id) for d in display_drivers]

    print(f"Всего водителей на маршруте: {len(route_drivers)}")
    print(f"ID для отображения: {', '.join(display_ids)}\n")

    # 2. Инициализация планировщика БЕЗ истории (чистый табель)
    analyzer = WorkforceAnalyzer(db)

    # Структура для хранения результатов
    results = {d_id: {} for d_id in display_ids}

    # 3. Моделирование по дням
    print("Запуск моделирования...")
    for day in range(START_DAY, END_DAY + 1):
        print(f"  День {day}...", end="\r")

        # ВАЖНО: Каждый день начинаем с чистого листа (без истории)
        # Это гарантирует, что мы работаем строго по табелю
        analyzer.history = {}

        result = analyzer.generate_daily_roster(ROUTE, day, MONTH, YEAR)

        if "error" in result:
            print(f"\n  ❌ День {day}: {result['error']}")
            continue

        # Парсим, кто где работал
        for tram in result.get("roster", []):
            # Утренняя смена
            if tram.get("shift_1"):
                driver_str = tram["shift_1"].get("driver")
                if driver_str:
                    d_id = driver_str.split(" ")[0]
                    if d_id in display_ids:
                        results[d_id][day] = f"В{tram['tram_number']}у"  # Вагон N утро

            # Вечерняя смена
            if tram.get("shift_2"):
                driver_str = tram["shift_2"].get("driver")
                if driver_str:
                    d_id = driver_str.split(" ")[0]
                    if d_id in display_ids:
                        # Если уже работал утром в этот день
                        if day in results[d_id]:
                            results[d_id][day] += f"+В{tram['tram_number']}в"
                        else:
                            results[d_id][day] = f"В{tram['tram_number']}в"  # Вагон N вечер

    print("\n")

    # 4. Формирование таблицы
    print("=== РЕЗУЛЬТАТ РАСПРЕДЕЛЕНИЯ ===\n")

    # Заголовок
    header = f"{'ID':<8} | {'График':<6} | {'Режим':<5} |"
    for d in range(START_DAY, END_DAY + 1):
        header += f" {d:^7} |"
    print(header)
    print("-" * len(header))

    # Строки водителей
    for driver in display_drivers:
        d_id = str(driver.id)

        # График и режим (если есть в модели)
        try:
            # Попробуем разные варианты имен атрибутов
            graph = getattr(driver, 'schedule_type', None) or \
                    getattr(driver, 'schedule', None) or \
                    getattr(driver, 'graph', None) or "?"
            mode = getattr(driver, 'mode', None) or \
                   getattr(driver, 'shift_mode', None) or "?"
        except:
            graph = "?"
            mode = "?"

        row = f"{d_id:<8} | {str(graph):<6} | {str(mode):<5} |"

        for day in range(START_DAY, END_DAY + 1):
            # План из табеля
            plan = driver.get_status_for_day(day)
            # Факт из моделирования
            fact = results[d_id].get(day, "")

            # Форматирование ячейки
            if plan == "В":  # Выходной по плану
                if fact:
                    cell = f"!{fact[:6]}"  # Ошибка: работал в выходной
                else:
                    cell = "В"
            elif plan in ["1", "2"]:  # Рабочий день
                if fact:
                    cell = fact[:7]  # Обрезаем если длинное
                else:
                    cell = f"{plan}/-"  # План есть, факта нет
            else:
                cell = "?"

            row += f" {cell:^7} |"

        print(row)

    # 5. Статистика
    print(f"\n=== СТАТИСТИКА ===")

    total_planned = 0
    total_assigned = 0

    for driver in display_drivers:
        for day in range(START_DAY, END_DAY + 1):
            plan = driver.get_status_for_day(day)
            if plan in ["1", "2"]:
                total_planned += 1
                if results[str(driver.id)].get(day):
                    total_assigned += 1

    print(f"Запланировано смен: {total_planned}")
    print(f"Распределено смен: {total_assigned}")
    if total_planned > 0:
        print(f"Эффективность: {total_assigned / total_planned * 100:.1f}%")

    # Сохранение в файл
    output_path = f"outputs/debug_{ROUTE}_{MONTH}_{START_DAY}-{END_DAY}.txt"
    os.makedirs("outputs", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"ОТЛАДКА РАСПРЕДЕЛЕНИЯ\n")
        f.write(f"Маршрут {ROUTE}, {START_DAY}-{END_DAY} {MONTH} {YEAR}\n\n")
        f.write(header + "\n")
        f.write("-" * len(header) + "\n")

        for driver in display_drivers:
            d_id = str(driver.id)
            row = f"{d_id:<8} |"
            for day in range(START_DAY, END_DAY + 1):
                plan = driver.get_status_for_day(day)
                fact = results[d_id].get(day, "-")
                row += f" {plan}/{fact[:3]:^6} |"
            f.write(row + "\n")

    print(f"\nРезультат сохранен: {output_path}")


if __name__ == "__main__":
    main()