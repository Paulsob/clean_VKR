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
SELECTED_ROUTE = "47"
SELECTED_MONTH = "Март"
SELECTED_YEAR = 2026
SIMULATION_MODE = "real"  # strict / real
SIMULATION_DURATION = 1

# Имя сценария (имя папки с результатами)
# ВАЖНО: Если вы хотите прочитать старые результаты из папки "mixed",
# назовите переменную "mixed". Если хотите новую папку - оставьте как есть.
SIMULATION_SCENARIO_NAME = "mix_optimization_v1"

# Список папок с данными
INPUT_PATTERNS = ["4x2", "5х2_holiday"]

# 3. НАСТРОЙКА ПУТЕЙ
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if USE_SYNTHETIC_DATA:
    ENV_FOLDER_NAME = "env_synthetic"
    _get_logger().info(f"РЕЖИМ СИНТЕТИКИ: Сценарий {SIMULATION_SCENARIO_NAME}. Источники: {INPUT_PATTERNS}")
else:
    ENV_FOLDER_NAME = "env_real"

ENV_DIR = os.path.join(BASE_DIR, ENV_FOLDER_NAME)
DATA_DIR = os.path.join(ENV_DIR, "data")

# Если синтетика - результаты и историю в папку СЦЕНАРИЯ
if USE_SYNTHETIC_DATA:
    RESULTS_DIR = os.path.join(DATA_DIR, "results", SIMULATION_SCENARIO_NAME)
    HISTORY_DIR = os.path.join(ENV_DIR, "history", SIMULATION_SCENARIO_NAME)
else:
    RESULTS_DIR = os.path.join(DATA_DIR, "results")
    HISTORY_DIR = os.path.join(ENV_DIR, "history")

OUTPUTS_DIR = os.path.join(ENV_DIR, "outputs")

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

# 5. ФОРМИРОВАНИЕ ИМЕН ФАЙЛОВ
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

# 7. НАСТРОЙКИ ВРЕМЕНИ И ОГРАНИЧЕНИЙ

# ОТДЫХ
# Минимальный отдых между сменами (в часах)
REST_MIN_HOURS_REAL = 12.0      # Режим Real: минимум 12 часов
REST_MIN_HOURS_STRICT = 12.0    # Режим Strict: минимум 12 часов (база)

# Множитель отдыха для STRICT режима
# Формула: Отдых >= Время_Работы * REST_MULTIPLIER_STRICT
# Если 2.0, то после 8 часов работы нужно 16 часов отдыха.
REST_MULTIPLIER_STRICT = 2.0

# ПЕРЕРАБОТКИ
# Порог "Мягкого потолка" (часов сверх нормы).
# Если водитель набрал Норму + SOFT_LIMIT, его приоритет резко падает,
# чтобы система перестала его назначать без крайней нужды.
OVERTIME_SOFT_LIMIT = 20.0

# Жесткий лимит переработки (часов сверх нормы).
# Если водитель набрал Норму + HARD_LIMIT, ему ЗАПРЕЩЕНО работать вообще.
OVERTIME_HARD_LIMIT = 40.0