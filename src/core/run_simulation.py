import sys
import os
import json
import calendar
from datetime import date
from typing import List, Dict
import logging

# Настройка путей
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import src.config as config
from src.prepare_data.database import DataLoader
from src.core.scheduler import WorkforceAnalyzer
from src.logger import get_logger
from src.constants import get_month_number
from src.common_utils import get_month_sequence, get_previous_month

logger = get_logger(__name__)
logging.getLogger("src.core.scheduler").setLevel(logging.WARNING)


def get_dynamic_paths(route_number, month_name, year, mode):
    sim_result_path = config.path_manager.get_simulation_file_path(
        route=route_number,
        month=month_name,
        year=year,
        mode=mode
    )
    new_history_path = config.path_manager.get_history_file_path(
        route=route_number,
        month=month_name,
        year=year,
        mode=mode
    )
    return sim_result_path, new_history_path


def identify_pattern_by_id(driver_id):
    """Определяет тип графика по диапазону ID."""
    try:
        did = int(driver_id)
        if did < 10000:
            return "4x2"
        elif 10000 <= did < 20000:
            return "5x2"
        elif 20000 <= did < 30000:
            return "5x2_holidays"
        else:
            return "Other"
    except:
        return "Unknown"


def run_simulation_sequence(routes_list, db, start_month, start_year, duration, mode):
    timeline = get_month_sequence(start_month, start_year, duration)
    logger.info(f"--- СТАРТ СИМУЛЯЦИИ: {timeline[0]} -> {timeline[-1]} ---")

    if config.USE_SYNTHETIC_DATA:
        logger.info(f"Сценарий: {config.SIMULATION_SCENARIO_NAME}")
        logger.info(f"Источники данных: {config.INPUT_PATTERNS}")

    analyzer = WorkforceAnalyzer(db)

    first_m_name, first_y = timeline[0]
    prev_month_name, prev_year = get_previous_month(first_m_name, first_y)

    try:
        loaded = analyzer.load_history_for_all_routes(routes_list, prev_month_name, prev_year)
        logger.info(f"История за {prev_month_name} загружена ({loaded} записей)")
    except Exception:
        logger.warning(f"История пуста. Старт с чистого листа.")

    for month_name, year in timeline:
        logger.info(f"\nРАСЧЕТ: {month_name} {year}")
        m_num = get_month_number(month_name)
        _, days_in_month = calendar.monthrange(year, m_num)

        results_by_route = {route: {} for route in routes_list}
        total_issues_in_month = 0
        monthly_driver_stats = {}

        for day in range(1, days_in_month + 1):
            daily_results = analyzer.generate_daily_roster_for_all_routes(
                routes_list, day, month_name, year, mode=mode
            )

            day_mix_stats = {}

            for route, data in daily_results.items():
                roster = data.get('roster', [])
                results_by_route[route][str(day)] = data

                for tram in roster:
                    if tram.get("issues"):
                        total_issues_in_month += len(tram["issues"])

                    for shift_key in ['shift_1', 'shift_2']:
                        shift_info = tram.get(shift_key)
                        if shift_info:
                            d_id = str(shift_info['driver'])

                            # Определяем тип графика по числу
                            prefix = identify_pattern_by_id(d_id)

                            day_mix_stats[prefix] = day_mix_stats.get(prefix, 0) + 1
                            monthly_driver_stats[d_id] = monthly_driver_stats.get(d_id, 0) + 1

            mix_str = ", ".join([f"{k}={v}" for k, v in day_mix_stats.items()])
            if not mix_str: mix_str = "Выходной / Нет рейсов"
            logger.info(f"   День {day:02d}: {mix_str}")

        logger.info("-" * 40)
        if total_issues_in_month > 0:
            logger.error(f"МЕСЯЦ ЗАВЕРШЕН С ОШИБКАМИ: {total_issues_in_month} дыр")
        else:
            logger.info(f"Месяц {month_name} закрыт идеально.")

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
    elif config.PROCESS_ALL_ROUTES and db.schedules:
        unique_routes = set(str(s.route_number) for s in db.schedules)
        routes_to_process = sorted(list(unique_routes), key=lambda x: int(x) if x.isdigit() else x)
    elif config.SELECTED_ROUTE:
        routes_to_process = [str(config.SELECTED_ROUTE)]
    else:
        logger.error("Не выбраны маршруты в config.py")
        return

    try:
        run_simulation_sequence(
            routes_to_process, db, target_month, target_year, target_duration, target_mode
        )
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {e}", exc_info=True)
        raise e


if __name__ == "__main__":
    main()