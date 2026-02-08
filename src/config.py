import os
from src.utils import get_month_number
from src.logger import get_logger

logger = get_logger(__name__)

# 1. ГЛАВНЫЙ ПЕРЕКЛЮЧАТЕЛЬ РЕЖИМА
# True  -> Работаем в папке env_synthetic
# False -> Работаем в папке env_real
USE_SYNTHETIC_DATA = True

# 2. ПАРАМЕТРЫ СИМУЛЯЦИИ
# True  -> Моделирование на все маршруты
# False -> Моделирование на SELECTED_ROUTE
PROCESS_ALL_ROUTES = False
SELECTED_ROUTE = "47"
SELECTED_MONTH = "Январь"
SELECTED_YEAR = 2026
SIMULATION_MODE = "strict"  # strict / real
SIMULATION_DURATION = 12   # длительность симуляции в месяцах

"""
Используется английская x
4x2
5x2
3x2x3x1
"""
SELECTED_PATTERN = "4x2"

# 3. НАСТРОЙКА ПУТЕЙ (ОКРУЖЕНИЯ)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if USE_SYNTHETIC_DATA:
    ENV_FOLDER_NAME = "env_synthetic"
    logger.info(f"РЕЖИМ СИНТЕТИКИ: Работаем в папке {ENV_FOLDER_NAME}, график {SELECTED_PATTERN}")
else:
    ENV_FOLDER_NAME = "env_real"

ENV_DIR = os.path.join(BASE_DIR, ENV_FOLDER_NAME)

DATA_DIR = os.path.join(ENV_DIR, "data")
HISTORY_DIR = os.path.join(ENV_DIR, "history")
OUTPUTS_DIR = os.path.join(ENV_DIR, "outputs")

# Если синтетика - кладем результаты и историю в подпапку графика (results/4x2/...)
if USE_SYNTHETIC_DATA and SELECTED_PATTERN:
    RESULTS_DIR = os.path.join(DATA_DIR, "results", SELECTED_PATTERN)
    HISTORY_DIR = os.path.join(ENV_DIR, "history", SELECTED_PATTERN)
else:
    RESULTS_DIR = os.path.join(DATA_DIR, "results")

# Создаем папки, если их нет
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

# 4. АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ПАПОК
# for path in [DATA_DIR, HISTORY_DIR, OUTPUTS_DIR, RESULTS_DIR]:
#     os.makedirs(path, exist_ok=True)

# 5. ФОРМИРОВАНИЕ ИМЕН ФАЙЛОВ
month_num = get_month_number(SELECTED_MONTH)
directory_name_common = f"{month_num:02d}_{SELECTED_MONTH}_{SELECTED_YEAR}"

# 5.1. Результат симуляции
filename_sim = f"simulation_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
SIMULATION_RESULT_FILE = os.path.join(
    RESULTS_DIR, directory_name_common, SIMULATION_MODE, filename_sim
)

# 5.2. История
filename_hist = f"history_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
HISTORY_FILE = os.path.join(
    HISTORY_DIR, directory_name_common, SIMULATION_MODE, filename_hist
)

# 5.3. Сводный отчет
filename_summary = f"summary_report_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SUMMARY_REPORT_FILE = os.path.join(
    OUTPUTS_DIR, "SUMMARY_REPORTS", directory_name_common, SIMULATION_MODE, filename_summary
)

# 5.4. Книга расписаний
filename_book = f"schedule_book_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SCHEDULE_BOOK_REPORT_FILE = os.path.join(
    OUTPUTS_DIR, "SCHEDULE_BOOKS", directory_name_common, SIMULATION_MODE, filename_book
)