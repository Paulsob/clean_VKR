import sys
import os
import json
import calendar
from datetime import date
from typing import List

# Настройка путей
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import src.config as config
from src.prepare_data.database import DataLoader
from src.core.scheduler import WorkforceAnalyzer
from src.logger import get_logger
from src.utils import get_month_number

logger = get_logger(__name__)


def get_month_sequence(start_month_name, start_year, duration_months):
    months_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    try:
        start_idx = get_month_number(start_month_name) - 1
    except:
        start_idx = 0
    sequence = []
    current_idx = start_idx
    current_year = start_year
    for _ in range(duration_months):
        m_name = months_names[current_idx]
        sequence.append((m_name, current_year))
        current_idx += 1
        if current_idx >= 12:
            current_idx = 0
            current_year += 1
    return sequence


def get_dynamic_paths(route_number, month_name, year, mode):
    m_num = get_month_number(month_name)
    folder_name = f"{m_num:02d}_{month_name}_{year}"

    sim_output_dir = os.path.join(config.RESULTS_DIR, folder_name, mode)
    hist_output_dir = os.path.join(config.HISTORY_DIR, folder_name, mode)

    os.makedirs(sim_output_dir, exist_ok=True)
    os.makedirs(hist_output_dir, exist_ok=True)

    res_filename = f"simulation_{mode}_{route_number}_{month_name}_{year}.json"
    sim_result_path = os.path.join(sim_output_dir, res_filename)

    hist_filename = f"history_{mode}_{route_number}_{month_name}_{year}.json"
    new_history_path = os.path.join(hist_output_dir, hist_filename)

    return sim_result_path, new_history_path


def run_simulation_sequence(routes_list, db, start_month, start_year, duration, mode):
    # 1. Генерация временной шкалы
    timeline = get_month_sequence(start_month, start_year, duration)
    logger.info(f"--- СТАРТ СИМУЛЯЦИИ: {timeline[0]} -> {timeline[-1]} ---")
    if config.USE_SYNTHETIC_DATA:
        logger.info(f"📊 График: {config.SELECTED_PATTERN}")

    analyzer = WorkforceAnalyzer(db)

    # 2. Загрузка предыстории
    months_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    first_m_name, first_y = timeline[0]
    first_m_num = get_month_number(first_m_name)

    if first_m_num == 1:
        prev_month_num = 12
        prev_year = first_y - 1
    else:
        prev_month_num = first_m_num - 1
        prev_year = first_y
    prev_month_name = months_names[prev_month_num - 1]

    try:
        loaded = analyzer.load_history_for_all_routes(routes_list, prev_month_name, prev_year)
        logger.info(f"История за {prev_month_name} загружена ({loaded} записей)")
    except Exception:
        logger.warning(f"История пуста. Старт с чистого листа.")

    # 3. ЦИКЛ ПО МЕСЯЦАМ
    # ... (предыдущий код внутри run_simulation_sequence)

    # 3. ЦИКЛ ПО МЕСЯЦАМ
    for month_name, year in timeline:
        logger.info(f"--> Расчет: {month_name} {year}")
        m_num = get_month_number(month_name)
        _, days_in_month = calendar.monthrange(year, m_num)

        # # --- БЛОК ОТЛАДКИ (ИСПРАВЛЕННЫЙ) ---
        # if month_name == "Январь":
        #     print("\n🔍 --- ОТЛАДКА ДАННЫХ (ЯНВАРЬ) ---")
        #
        #     # 1. Пытаемся достать водителя из db.drivers
        #     test_driver = None
        #     if hasattr(db, 'drivers') and db.drivers:
        #         if isinstance(db.drivers, list) and len(db.drivers) > 0:
        #             test_driver = db.drivers[0]
        #         elif isinstance(db.drivers, dict) and len(db.drivers) > 0:
        #             # Если водители хранятся в словаре {id: Driver}
        #             test_driver = list(db.drivers.values())[0]
        #
        #     if test_driver is None:
        #         print("❌ ОШИБКА: Список водителей (db.drivers) пуст или не найден!")
        #     else:
        #         # Выводим инфо о водителе
        #         t_num = getattr(test_driver, 'tab_number', 'Нет атрибута tab_number')
        #         print(f"Водитель найден! Таб.№: {t_num}")
        #
        #         # 2. Проверяем расписание
        #         sched = getattr(test_driver, 'schedule', {})
        #         print(f"Тип хранилища расписания: {type(sched)}")
        #
        #         if isinstance(sched, dict):
        #             keys = list(sched.keys())
        #             if not keys:
        #                 print("⚠️ Расписание водителя пустое!")
        #             else:
        #                 first_key = keys[0]
        #                 print(f"Тип ключей (дней) в расписании: {type(first_key)} (Пример: {first_key})")
        #
        #                 # Проверяем наличие 31-го числа
        #                 val_int = sched.get(31)
        #                 val_str = sched.get("31")
        #                 print(f"Поиск 31 (int): {val_int}")
        #                 print(f"Поиск '31' (str): {val_str}")
        #
        #                 if val_int is None and val_str is None:
        #                     print("❌ ДАННЫХ ЗА 31 ЧИСЛО В ПАМЯТИ ВОДИТЕЛЯ НЕТ!")
        #                     print(f"Доступные дни (последние 5): {keys[-5:]}")
        #         else:
        #             print(f"⚠️ Расписание не словарь, а: {sched}")
        #
        #     print("-----------------------------------\n")
        # # --- КОНЕЦ БЛОКА ОТЛАДКИ ---

        results_by_route = {route: {} for route in routes_list}

        # Счетчик проблем для отчета
        total_issues_in_month = 0

        for day in range(1, days_in_month + 1):
            daily_results = analyzer.generate_daily_roster_for_all_routes(
                routes_list, day, month_name, year, mode=mode
            )

            # --- ПРОВЕРКА НЕХВАТКИ ВОДИТЕЛЕЙ ---
            for route, data in daily_results.items():
                roster = data.get('roster', [])
                missing_count = 0
                for tram in roster:
                    # Если есть issues, значит смену не закрыли
                    if tram.get("issues"):
                        missing_count += len(tram["issues"])

                if missing_count > 0:
                    total_issues_in_month += missing_count
                    # Логируем конкретный день
                    logger.error(
                        f"🚨 НЕХВАТКА: Маршрут {route}, День {day} ({month_name}). Дыр в расписании: {missing_count}")

                results_by_route[route][str(day)] = data

        # Итоги месяца
        if total_issues_in_month > 0:
            logger.error(f"❌ МЕСЯЦ {month_name} {year} ЗАВЕРШЕН С ОШИБКАМИ!")
            logger.error(f"   Всего незакрытых смен: {total_issues_in_month}")
            logger.error(f"   👉 РЕКОМЕНДАЦИЯ: Добавьте больше водителей для графика {config.SELECTED_PATTERN}!")
        else:
            logger.info(f"✅ Месяц {month_name} {year} закрыт идеально (0 дыр).")

        # Сохранение результатов
        for route in routes_list:
            sim_path, hist_path = get_dynamic_paths(route, month_name, year, mode)
            with open(sim_path, "w", encoding="utf-8") as f:
                json.dump(results_by_route[route], f, ensure_ascii=False, indent=2, default=str)

            route_history = analyzer.get_history_serializable()
            with open(hist_path, "w", encoding="utf-8") as f:
                json.dump(route_history, f, ensure_ascii=False, indent=2)

    logger.info("=== СИМУЛЯЦИЯ ЗАВЕРШЕНА ===")


def main(month=None, year=None, duration=None, routes=None, mode=None):
    target_month = month or config.SELECTED_MONTH
    target_year = year or config.SELECTED_YEAR
    target_duration = duration or config.SIMULATION_DURATION
    target_mode = mode or config.SIMULATION_MODE

    db = DataLoader()
    db.load_all()

    if routes:
        routes_to_process = routes
    elif config.PROCESS_ALL_ROUTES:
        unique_routes = set(str(s.route_number) for s in db.schedules)
        routes_to_process = sorted(list(unique_routes), key=lambda x: int(x) if x.isdigit() else x)
    else:
        routes_to_process = [str(config.SELECTED_ROUTE)]

    try:
        run_simulation_sequence(
            routes_to_process, db, target_month, target_year, target_duration, target_mode
        )
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {e}", exc_info=True)
        raise e


if __name__ == "__main__":
    main()