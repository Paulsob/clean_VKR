import os
from src.parsers.get_number_of_month import get_month_number

# === ГЛАВНЫЕ НАСТРОЙКИ МОДЕЛИРОВАНИЯ ===
SELECTED_ROUTE = "47"       # Номер маршрута (строка)
SELECTED_MONTH = "Январь"   # Месяц (русское название)
SELECTED_YEAR = 2026        # Год

# Режим расчета:
# 'strict' - строго соблюдать правила отдыха (возможны дыры в расписании)
# 'real' - назначать уставших водителей, но помечать нарушения
SIMULATION_MODE = "real"

# === ПУТИ К ФАЙЛАМ ===
# Определяем корень проекта динамически
# (поднимаемся на уровень выше от src/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(DATA_DIR, "results")
HISTORY_DIR = os.path.join(BASE_DIR, "history")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

# Имена файлов (генерируются автоматически на основе настроек)

# Получаем номер месяца
month_num = get_month_number(SELECTED_MONTH)
# Формируем полное имя файла с префиксом в виде двузначного номера
directory_name_simulation = f"{month_num:02d}_{SELECTED_MONTH}_{SELECTED_YEAR}"
filename = f"simulation_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
SIMULATION_RESULT_FILE = os.path.join(
    RESULTS_DIR, directory_name_simulation, filename
)


directory_name_history = f"{month_num:02d}_{SELECTED_MONTH}_{SELECTED_YEAR}"
filename = f"history_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
HISTORY_FILE = os.path.join(
    HISTORY_DIR, directory_name_history, filename
)


directory_name_summary_report = f"{month_num:02d}_{SELECTED_MONTH}_{SELECTED_YEAR}"
filename = f"summary_report_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SUMMARY_REPORT_FILE = os.path.join(
    OUTPUTS_DIR, "SUMMARY_REPORTS", directory_name_summary_report, filename
)



directory_name_summary_report = f"{month_num:02d}_{SELECTED_MONTH}_{SELECTED_YEAR}"
filename = f"schedule_book_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
SCHEDULE_BOOK_REPORT_FILE = os.path.join(
    OUTPUTS_DIR, "SCHEDULE_BOOKS", directory_name_summary_report, filename
)

