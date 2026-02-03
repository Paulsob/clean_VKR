import sys
import os
import json
import calendar
from datetime import date
from typing import List, Optional

# Настройка путей
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Импортируем конфиг как фолбэк (значения по умолчанию)
import src.config as config
from src.prepare_data.database import DataLoader
from src.core.scheduler import WorkforceAnalyzer
from src.logger import get_logger
from src.utils import get_month_number

logger = get_logger(__name__)


def get_dynamic_paths(route_number, month_name, year, mode):
    """Принимает mode как аргумент"""
    m_num = get_month_number(month_name)
    folder_name = f"{m_num:02d}_{month_name}_{year}"

    # Используем пути из конфига, но подставляем переданный mode
    sim_output_dir = os.path.join(config.RESULTS_DIR, folder_name, mode)
    hist_output_dir = os.path.join(config.HISTORY_DIR, folder_name, mode)

    os.makedirs(sim_output_dir, exist_ok=True)
    os.makedirs(hist_output_dir, exist_ok=True)

    res_filename = f"simulation_{mode}_{route_number}_{month_name}_{year}.json"
    sim_result_path = os.path.join(sim_output_dir, res_filename)

    hist_filename = f"history_{mode}_{route_number}_{month_name}_{year}.json"
    new_history_path = os.path.join(hist_output_dir, hist_filename)

    return sim_result_path, new_history_path


def run_for_all_routes(routes_list, db, month_name, year, mode):
    logger.info(f"--- Начало расчета маршрутов: {routes_list} (Режим: {mode}) ---")
    analyzer = WorkforceAnalyzer(db)

    # 1. Загрузка истории
    months_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    try:
        curr_m_num = get_month_number(month_name)
        prev_month_num, prev_year = (12, year - 1) if curr_m_num == 1 else (curr_m_num - 1, year)
        prev_month_name = months_names[prev_month_num - 1]

        loaded_records = analyzer.load_history_for_all_routes(routes_list, prev_month_name, prev_year)
        logger.info(f"Загружена история за {prev_month_name}: {loaded_records} записей")
    except Exception as e:
        logger.error(f"Ошибка загрузки истории: {e}")

    # 2. Расчет по дням
    m_num = get_month_number(month_name)
    _, days_in_month = calendar.monthrange(year, m_num)
    results_by_route = {route: {} for route in routes_list}

    for day in range(1, days_in_month + 1):
        daily_results = analyzer.generate_daily_roster_for_all_routes(
            routes_list, day, month_name, year, mode=mode
        )
        for route, result in daily_results.items():
            results_by_route[route][str(day)] = result

    # 3. Сохранение
    for route in routes_list:
        sim_path, hist_path = get_dynamic_paths(route, month_name, year, mode)
        with open(sim_path, "w", encoding="utf-8") as f:
            json.dump(results_by_route[route], f, ensure_ascii=False, indent=2, default=str)

        route_history = analyzer.get_history_serializable()
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(route_history, f, ensure_ascii=False, indent=2)

    logger.info(f"Обработка завершена: {len(routes_list)} маршрутов.")


def main(month=None, year=None, routes=None, mode=None):
    """
    Универсальная точка входа. Параметры берутся либо из API, либо из config.py
    """
    logger.info("=== ЗАПУСК СИМУЛЯЦИИ ===")

    # Расставляем приоритеты (Аргумент -> Конфиг)
    target_month = month or config.SELECTED_MONTH
    target_year = year or config.SELECTED_YEAR
    target_mode = mode or config.SIMULATION_MODE

    db = DataLoader()
    db.load_all()

    # Определяем список маршрутов
    if routes:  # Переданы из API
        routes_to_process = routes
    elif config.PROCESS_ALL_ROUTES:  # Флаг в конфиге
        unique_routes = set(str(s.route_number) for s in db.schedules)
        routes_to_process = sorted(list(unique_routes), key=lambda x: int(x) if x.isdigit() else x)
    else:  # Один маршрут из конфига
        routes_to_process = [str(config.SELECTED_ROUTE)]

    # Исправлено: убрал цикл, так как run_for_all_routes сам проходит по списку
    try:
        run_for_all_routes(routes_to_process, db, target_month, target_year, target_mode)
    except Exception as e:
        logger.error(f"!!! КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
        raise e


if __name__ == "__main__":
    main()