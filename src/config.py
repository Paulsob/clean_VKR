import os
from src.utils import get_month_number

# Если True: планировщик прогонит все маршруты
# Если False: планировщик прогонит только SELECTED_ROUTE
PROCESS_ALL_ROUTES = True

SELECTED_ROUTE = "47"
SELECTED_MONTH = "Январь"
SELECTED_YEAR = 2026

# strict - строго (с дырами),
# real - реально (с переработками/отгулами)
SIMULATION_MODE = "real"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(DATA_DIR, "results")
HISTORY_DIR = os.path.join(BASE_DIR, "history")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

month_num = get_month_number(SELECTED_MONTH)

# Общая папка месяца (например "01_Январь_2026")
directory_name_common = f"{month_num:02d}_{SELECTED_MONTH}_{SELECTED_YEAR}"


# 1. Результат симуляции (JSON)
# data/results/01_Январь_2026/real/simulation_real_47_Январь_2026.json
filename_sim = f"simulation_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
SIMULATION_RESULT_FILE = os.path.join(
    DATA_DIR, "results", directory_name_common, SIMULATION_MODE, filename_sim
)

# 2. История (JSON)
# history/01_Январь_2026/real/history_real_47_Январь_2026.json
filename_hist = f"history_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
HISTORY_FILE = os.path.join(
    HISTORY_DIR, directory_name_common, SIMULATION_MODE, filename_hist
)

# 3. Сводный отчет (XLSX)
# outputs/SUMMARY_REPORTS/01_Январь_2026/real/summary_report_real_47_Январь_2026.xlsx
filename_summary = f"summary_report_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SUMMARY_REPORT_FILE = os.path.join(
    OUTPUTS_DIR, "SUMMARY_REPORTS", directory_name_common, SIMULATION_MODE, filename_summary
)

# 4. Книга расписаний (XLSX)
# outputs/SCHEDULE_BOOKS/01_Январь_2026/real/schedule_book_real_47_Январь_2026.xlsx
filename_book = f"schedule_book_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SCHEDULE_BOOK_REPORT_FILE = os.path.join(
    OUTPUTS_DIR, "SCHEDULE_BOOKS", directory_name_common, SIMULATION_MODE, filename_book
)