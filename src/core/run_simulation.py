import sys
import os
import json
import calendar
from datetime import date


"""
25.01.2026
00:18
ЛОКАЛЬНАЯ ВЕТКА: feature/simulate_all_park
   ВЕТКА GITHUB: feature/
@@@@@@@@@@@@@@ ОБРАТИ ВНИМАНИЕ @@@@@@@@@@@@@@
НА ЭТОМ ЭТАПЕ Я НЕ УВЕРЕН, ЧТО 
ВОДИТЕЛИ ИЗ РЕЗЕРВА РАСПРЕДЕЛЯЮТСЯ ПРАВИЛЬНО
ВОЗМОЖНО, ОШИБКА В ЛОГИКЕ ПОЗВОЛЯЕТ ИМ ВСТАВАТЬ
НА ЛЮБЫЕ СМЕНЫ ЛЮБЫХ МАРШРУТОВ,
НЕЗАВИСИМО ОТ ЗАНЯТОСТИ И ОТДЫХА
@@@@@@@@@@@@@@ ОБРАТИ ВНИМАНИЕ @@@@@@@@@@@@@@
"""


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
os.chdir(project_root)

from src.config import (
    SELECTED_ROUTE, SELECTED_MONTH, SELECTED_YEAR, SIMULATION_MODE,
    PROCESS_ALL_ROUTES,
    RESULTS_DIR, HISTORY_DIR  # Импортируем только базовые папки
)
from src.prepare_data.database import DataLoader
from src.core.scheduler import WorkforceAnalyzer
from src.logger import get_logger
from src.utils import get_month_number

logger = get_logger(__name__)


def get_dynamic_paths(route_number, month_name, year):
    """
    Генерирует пути к файлам результатов и истории для конкретного маршрута.
    """
    m_num = get_month_number(month_name)
    folder_name = f"{m_num:02d}_{month_name}_{year}"

    # 1. Путь для сохранения результата симуляции
    res_filename = f"simulation_{route_number}_{month_name}_{year}.json"
    sim_result_path = os.path.join(RESULTS_DIR, folder_name, res_filename)

    # 2. Путь для сохранения новой истории (текущий месяц)
    hist_filename = f"history_{route_number}_{month_name}_{year}.json"
    new_history_path = os.path.join(HISTORY_DIR, folder_name, hist_filename)

    return sim_result_path, new_history_path


# СТАРАЯ ВЕРСИЯ - ЗАКОММЕНТИРОВАНА
# def run_for_single_route(route, db, month_name, year, mode):
#     """
#     Логика расчета для ОДНОГО маршрута.
#     """
#     logger.info(f"--- Начало расчета маршрута: {route} ---")
#
#     # Инициализируем анализатор заново для каждого маршрута,
#     # чтобы история и кэши не пересекались
#     analyzer = WorkforceAnalyzer(db)
#
#     # --------------------------------------------------------
#     # 1. Загрузка истории ПРОШЛОГО месяца
#     # --------------------------------------------------------
#     months_names = [
#         "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
#         "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
#     ]
#
#     try:
#         curr_m_num = get_month_number(month_name)
#         if curr_m_num == 1:
#             prev_month_num = 12
#             prev_year = year - 1
#         else:
#             prev_month_num = curr_m_num - 1
#             prev_year = year
#
#         prev_month_name = months_names[prev_month_num - 1]
#
#         # Путь к истории прошлого месяца
#         prev_folder = f"{prev_month_num:02d}_{prev_month_name}_{prev_year}"
#         prev_file = f"history_{route}_{prev_month_name}_{prev_year}.json"
#         prev_hist_path = os.path.join(HISTORY_DIR, prev_folder, prev_file)
#
#         if os.path.exists(prev_hist_path):
#             with open(prev_hist_path, "r", encoding="utf-8") as f:
#                 hist_data = json.load(f)
#                 analyzer.load_history(hist_data)
#                 logger.info(f"[{route}] Загружена история за {prev_month_name}: {len(hist_data)} записей")
#         else:
#             logger.warning(f"[{route}] История за {prev_month_name} не найдена ({prev_file}). Старт с нуля.")
#
#     except Exception as e:
#         logger.error(f"[{route}] Ошибка загрузки истории: {e}")
#
#     # --------------------------------------------------------
#     # 2. Расчет по дням
#     # --------------------------------------------------------
#     m_num = get_month_number(month_name)
#     _, days_in_month = calendar.monthrange(year, m_num)
#     full_results = {}
#
#     for day in range(1, days_in_month + 1):
#         res = analyzer.generate_daily_roster(
#             route, day, month_name, year, mode=mode
#         )
#         full_results[str(day)] = res
#
#     # --------------------------------------------------------
#     # 3. Сохранение результатов
#     # --------------------------------------------------------
#     sim_path, hist_path = get_dynamic_paths(route, month_name, year)
#
#     # Сохраняем расписание
#     os.makedirs(os.path.dirname(sim_path), exist_ok=True)
#     with open(sim_path, "w", encoding="utf-8") as f:
#         json.dump(full_results, f, ensure_ascii=False, indent=2, default=str)
#
#     # Сохраняем новую историю
#     os.makedirs(os.path.dirname(hist_path), exist_ok=True)
#     with open(hist_path, "w", encoding="utf-8") as f:
#         json.dump(analyzer.get_history_serializable(), f, ensure_ascii=False, indent=2)
#
#     logger.info(f"[{route}] Готово. Файлы сохранены.")


def run_for_all_routes(routes_list, db, month_name, year, mode):
    """
    Новая логика расчета для ВСЕХ маршрутов одновременно.
    Решает проблему межмаршрутных конфликтов водителей ANY.
    """
    logger.info(f"--- Начало расчета всех маршрутов: {routes_list} ---")

    # Инициализируем ОДИН анализатор для всех маршрутов
    analyzer = WorkforceAnalyzer(db)

    # --------------------------------------------------------
    # 1. Загрузка истории ПРОШЛОГО месяца для всех маршрутов
    # --------------------------------------------------------
    months_names = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]

    try:
        curr_m_num = get_month_number(month_name)
        if curr_m_num == 1:
            prev_month_num = 12
            prev_year = year - 1
        else:
            prev_month_num = curr_m_num - 1
            prev_year = year

        prev_month_name = months_names[prev_month_num - 1]

        # Загружаем историю всех маршрутов
        loaded_records = analyzer.load_history_for_all_routes(routes_list, prev_month_name, prev_year)
        logger.info(f"Загружена объединенная история за {prev_month_name}: {loaded_records} записей")

    except Exception as e:
        logger.error(f"Ошибка загрузки истории: {e}")

    # --------------------------------------------------------
    # 2. Расчет по дням для всех маршрутов одновременно
    # --------------------------------------------------------
    m_num = get_month_number(month_name)
    _, days_in_month = calendar.monthrange(year, m_num)

    # Структура: {route: {day: result}}
    results_by_route = {route: {} for route in routes_list}

    for day in range(1, days_in_month + 1):
        # Генерируем расписание для всех маршрутов одновременно
        daily_results = analyzer.generate_daily_roster_for_all_routes(
            routes_list, day, month_name, year, mode=mode
        )

        # Распределяем результаты по маршрутам
        for route, result in daily_results.items():
            results_by_route[route][str(day)] = result

    # --------------------------------------------------------
    # 3. Сохранение результатов по маршрутам (как раньше)
    # --------------------------------------------------------
    for route in routes_list:
        sim_path, hist_path = get_dynamic_paths(route, month_name, year)

        # Сохраняем расписание маршрута
        os.makedirs(os.path.dirname(sim_path), exist_ok=True)
        with open(sim_path, "w", encoding="utf-8") as f:
            json.dump(results_by_route[route], f, ensure_ascii=False, indent=2, default=str)

        # Сохраняем историю маршрута (фильтруем по водителям этого маршрута)
        route_history = analyzer.get_history_serializable()
        os.makedirs(os.path.dirname(hist_path), exist_ok=True)
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(route_history, f, ensure_ascii=False, indent=2)

    logger.info(f"Готово. Обработано {len(routes_list)} маршрутов.")


def main():
    logger.info("=== ЗАПУСК МАССОВОЙ СИМУЛЯЦИИ ===")

    # 1. Загрузка базы данных (один раз для всех)
    logger.info("Загрузка базы данных...")
    db = DataLoader()
    db.load_all()

    # 2. Определение списка маршрутов
    routes_to_process = []

    if PROCESS_ALL_ROUTES:
        # Извлекаем все уникальные маршруты из расписания
        # db.schedules - это список объектов RouteSchedule
        unique_routes = set()
        for s in db.schedules:
            unique_routes.add(str(s.route_number))

        # Сортируем (как числа, если это числа, иначе как строки)
        routes_to_process = sorted(list(unique_routes), key=lambda x: int(x) if x.isdigit() else x)
        logger.info(f"Режим ALL: Найдено {len(routes_to_process)} маршрутов: {routes_to_process}")
    else:
        routes_to_process = [str(SELECTED_ROUTE)]
        logger.info(f"Режим SINGLE: Маршрут {SELECTED_ROUTE}")

    # 3. Запуск цикла
    total = len(routes_to_process)
    for i, route in enumerate(routes_to_process, 1):
        logger.info(f">>> Обработка маршрута {route} ({i}/{total})")
        # Запуск нового алгоритма (все маршруты одновременно)
        try:
            run_for_all_routes(routes_to_process, db, SELECTED_MONTH, SELECTED_YEAR, SIMULATION_MODE)
        except Exception as e:
            logger.error(f"!!! КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)

    logger.info("=== Все маршруты обработаны")


if __name__ == "__main__":
    main()