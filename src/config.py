import os

# === ГЛАВНЫЕ НАСТРОЙКИ МОДЕЛИРОВАНИЯ ===
SELECTED_ROUTE = "47"       # Номер маршрута (строка)
SELECTED_MONTH = "Февраль"  # Месяц (русское название)
SELECTED_YEAR = 2026        # Год

# Режим расчета:
# 'strict' - строго соблюдать правила отдыха (возможны дыры в расписании)
# 'real'   - назначать уставших водителей, но помечать нарушения
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
SIMULATION_RESULT_FILE = os.path.join(
    RESULTS_DIR, f"simulation_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
)

HISTORY_FILE = os.path.join(
    HISTORY_DIR, f"history_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.json"
)

REPORT_FILE = os.path.join(
    OUTPUTS_DIR, f"summary_report_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
)