import os
from src.utils import get_month_number


# Если True: скрипт найдет все маршруты и прогонит их (SELECTED_ROUTE игнорируется)
# Если False: скрипт прогонит только SELECTED_ROUTE
PROCESS_ALL_ROUTES = True

SELECTED_ROUTE = "47"       # Номер маршрута (дефолтный)
SELECTED_MONTH = "Январь"  # Месяц
SELECTED_YEAR = 2026        # Год

# 'strict' - строго (с дырами), 'real' - реально (с переработками/отгулами)
SIMULATION_MODE = "real"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(DATA_DIR, "results")
HISTORY_DIR = os.path.join(BASE_DIR, "history")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

# Эти пути рассчитываются для SELECTED_ROUTE.
# 1. Если PROCESS_ALL_ROUTES = False, мы используем их.
# 2. Если PROCESS_ALL_ROUTES = True, скрипт run_simulation.py их ПРОИГНОРИРУЕТ
#    и создаст свои пути внутри цикла. Но удалять их нельзя, чтобы не сломать импорты.

month_num = get_month_number(SELECTED_MONTH)

# Папки по месяцам (например "02_Февраль_2026")
directory_name_common = f"{month_num:02d}_{SELECTED_MONTH}_{SELECTED_YEAR}"

# 1. Результат симуляции (JSON)
filename_sim = f"simulation_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
SIMULATION_RESULT_FILE = os.path.join(
    RESULTS_DIR, directory_name_common, filename_sim
)

# 2. История (JSON)
filename_hist = f"history_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
HISTORY_FILE = os.path.join(
    HISTORY_DIR, directory_name_common, filename_hist
)

# 3. Сводный отчет (XLSX)
filename_summary = f"summary_report_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SUMMARY_REPORT_FILE = os.path.join(
    OUTPUTS_DIR, "SUMMARY_REPORTS", directory_name_common, filename_summary
)

# 4. Книга расписаний (XLSX)
filename_book = f"schedule_book_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SCHEDULE_BOOK_REPORT_FILE = os.path.join(
    OUTPUTS_DIR, "SCHEDULE_BOOKS", directory_name_common, filename_book
)