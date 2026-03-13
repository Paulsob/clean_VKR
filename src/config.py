import os
from src.constants import get_month_number

_logger = None
def _get_logger():
    global _logger
    if _logger is None:
        from src.logger import get_logger
        _logger = get_logger(__name__)
    return _logger

USE_SYNTHETIC_DATA = True

PROCESS_ALL_ROUTES = False
SELECTED_ROUTE = "9"
SELECTED_MONTH = "Март"
SELECTED_YEAR = 2026
SIMULATION_MODE = "strict"  # strict / real
SIMULATION_DURATION = 1


PUBLIC_HOLIDAYS = [
    "2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09",
    "2026-02-23", "2026-02-24",
    "2026-03-09",
    "2026-05-01", "2026-05-04", "2026-05-05",
    "2026-05-11",
    "2026-06-12",
    "2026-11-04",
    "2026-12-31",
]

WORKING_WEEKENDS = []

SIMULATION_SCENARIO_NAME = "mix_optimization_v1"

INPUT_PATTERNS = ["4x2"]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if USE_SYNTHETIC_DATA:
    ENV_FOLDER_NAME = "env_synthetic"
    _get_logger().info(f"РЕЖИМ СИНТЕТИКИ: Сценарий {SIMULATION_SCENARIO_NAME}. Источники: {INPUT_PATTERNS}")
else:
    ENV_FOLDER_NAME = "env_real"

ENV_DIR = os.path.join(BASE_DIR, ENV_FOLDER_NAME)
DATA_DIR = os.path.join(ENV_DIR, "data")

if USE_SYNTHETIC_DATA:
    RESULTS_DIR = os.path.join(DATA_DIR, "results", SIMULATION_SCENARIO_NAME)
    HISTORY_DIR = os.path.join(ENV_DIR, "history", SIMULATION_SCENARIO_NAME)
else:
    RESULTS_DIR = os.path.join(DATA_DIR, "results")
    HISTORY_DIR = os.path.join(ENV_DIR, "history")

OUTPUTS_DIR = os.path.join(ENV_DIR, "outputs")

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

month_num = get_month_number(SELECTED_MONTH)
directory_name_common = f"{month_num:02d}_{SELECTED_MONTH}_{SELECTED_YEAR}"

# 5.1. Результат симуляции
filename_sim = f"simulation_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
SIMULATION_RESULT_FILE = os.path.join(RESULTS_DIR, directory_name_common, SIMULATION_MODE, filename_sim)

# 5.2. История
filename_hist = f"history_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
HISTORY_FILE = os.path.join(HISTORY_DIR, directory_name_common, SIMULATION_MODE, filename_hist)

# 5.3. Сводный отчет
filename_summary = f"summary_{SIMULATION_SCENARIO_NAME}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SUMMARY_REPORT_FILE = os.path.join(OUTPUTS_DIR, "SUMMARY_REPORTS", directory_name_common, SIMULATION_MODE, filename_summary)

# 5.4. Книга расписаний
filename_book = f"schedule_book_{SIMULATION_SCENARIO_NAME}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SCHEDULE_BOOK_REPORT_FILE = os.path.join(OUTPUTS_DIR, "SCHEDULE_BOOKS", directory_name_common, SIMULATION_MODE, filename_book)

# 6. PATH MANAGER
from src.path_manager import PathManager
path_manager = PathManager(
    base_dir=BASE_DIR,
    use_synthetic=USE_SYNTHETIC_DATA,
    selected_pattern=SIMULATION_SCENARIO_NAME
)
path_manager.ensure_directories()

WORK_MIN_HOURS = 2.0            # Минимальная смена
WORK_MAX_HOURS_STANDARD = 10.0  # Стандартный максимум
WORK_MAX_HOURS_EXTENDED = 12.0  # Максимум по согласованию (разрешено в Real)

# ЕЖЕДНЕВНЫЙ ОТДЫХ
# Базовое правило: Отдых >= Работа * REST_MULTIPLIER
REST_MULTIPLIER = 2.0

# Исключение: Можно сокращать отдых до этого значения...
REST_MIN_REDUCED = 12.0

# ...но не более стольких раз за неделю (между выходными 42ч+)
REST_REDUCTIONS_LIMIT_STRICT = 2  # Для Strict
REST_REDUCTIONS_LIMIT_REAL = 99   # Для Real (отключаем счетчик, разрешаем всегда до 9-12ч)

# ПЕРЕРАБОТКИ (МЕСЯЦ)
OVERTIME_SOFT_LIMIT = 20.0  # Мягкий потолок
OVERTIME_HARD_LIMIT = 40.0  # Жесткий потолок (ТК РФ: 120ч в год ~ 10-20 в месяц, но мы берем запас)