import os
from src.utils import get_month_number
from src.logger import get_logger

logger = get_logger(__name__)

# 1. ГЛАВНЫЙ ПЕРЕКЛЮЧАТЕЛЬ РЕЖИМА
# True  -> Работаем в папке env_synthetic
# False -> Работаем в папке env_real
USE_SYNTHETIC_DATA = True

# 2. ПАРАМЕТРЫ СИМУЛЯЦИИ
PROCESS_ALL_ROUTES = True
SELECTED_ROUTE = "47"
SELECTED_MONTH = "Январь"
SELECTED_YEAR = 2026
SIMULATION_MODE = "real"  # strict / real

# 3. НАСТРОЙКА ПУТЕЙ (ОКРУЖЕНИЯ)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Выбираем имя главной папки окружения
if USE_SYNTHETIC_DATA:
    ENV_FOLDER_NAME = "env_synthetic"
    logger.info(f"РЕЖИМ СИНТЕТИКИ: Работаем в папке {ENV_FOLDER_NAME}")
else:
    ENV_FOLDER_NAME = "env_real"

# Полный путь к текущему рабочему окружению
ENV_DIR = os.path.join(BASE_DIR, ENV_FOLDER_NAME)

# Теперь все рабочие папки лежат ВНУТРИ выбранного окружения.
# Это гарантирует идеальный порядок.
DATA_DIR = os.path.join(ENV_DIR, "data")
HISTORY_DIR = os.path.join(ENV_DIR, "history")
OUTPUTS_DIR = os.path.join(ENV_DIR, "outputs")

# Результаты симуляции (JSON) по старой логике лежат внутри data
RESULTS_DIR = os.path.join(DATA_DIR, "results")

# 4. АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ПАПОК (Опционально, но удобно)
# for path in [DATA_DIR, HISTORY_DIR, OUTPUTS_DIR, RESULTS_DIR]:
#     os.makedirs(path, exist_ok=True)

# 5. ФОРМИРОВАНИЕ ИМЕН ФАЙЛОВ
month_num = get_month_number(SELECTED_MONTH)
directory_name_common = f"{month_num:02d}_{SELECTED_MONTH}_{SELECTED_YEAR}"

# 1. Результат симуляции
filename_sim = f"simulation_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
SIMULATION_RESULT_FILE = os.path.join(
    RESULTS_DIR, directory_name_common, SIMULATION_MODE, filename_sim
)

# 2. История
filename_hist = f"history_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
HISTORY_FILE = os.path.join(
    HISTORY_DIR, directory_name_common, SIMULATION_MODE, filename_hist
)

# 3. Сводный отчет
filename_summary = f"summary_report_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SUMMARY_REPORT_FILE = os.path.join(
    OUTPUTS_DIR, "SUMMARY_REPORTS", directory_name_common, SIMULATION_MODE, filename_summary
)

# 4. Книга расписаний
filename_book = f"schedule_book_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SCHEDULE_BOOK_REPORT_FILE = os.path.join(
    OUTPUTS_DIR, "SCHEDULE_BOOKS", directory_name_common, SIMULATION_MODE, filename_book
)