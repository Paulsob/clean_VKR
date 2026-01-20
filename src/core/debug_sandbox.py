import sys
import os

# Настройка путей
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
os.chdir(project_root)

from src.database import DataLoader
from src.scheduler import WorkforceAnalyzer

# === НАСТРОЙКИ ТЕСТА ===
ROUTE = "47"
MONTH = "Февраль"
YEAR = 2026
TEST_DAYS = 10
DRIVERS_TO_SHOW = 15
MODE = "strict"  # 'real' или 'strict'


def main():
    print(f"=== SANDBOX TEST ({MODE.upper()}) ===")

    db = DataLoader()
    db.load_all()

    all_drivers = [d for d in db.drivers if str(d.assigned_route_number) == str(ROUTE) and d.month == MONTH]
    if not all_drivers:
        print("Водители не найдены!")
        return

    display_ids = [str(d.id) for d in all_drivers[:DRIVERS_TO_SHOW]]

    # Инициализация (история пустая)
    analyzer = WorkforceAnalyzer(db)

    # Таблица результатов
    results = {did: {} for did in display_ids}

    print("Запуск симуляции по дням...")
    for day in range(1, TEST_DAYS + 1):
        res = analyzer.generate_daily_roster(ROUTE, day, MONTH, YEAR, mode=MODE)

        if "roster" in res:
            for tram in res["roster"]:
                for shift_key in ["shift_1", "shift_2"]:
                    shift_data = tram.get(shift_key)
                    if shift_data and shift_data.get("driver"):
                        did = shift_data["driver"].split(" ")[0]
                        if did in display_ids:
                            val = "1" if shift_key == "shift_1" else "2"
                            if shift_data.get("warnings"):
                                val += "!"
                            results[did][day] = val

    # Вывод
    print("\n" + "=" * 60)
    print(f"{'ID':<6} |", end="")
    for d in range(1, TEST_DAYS + 1): print(f" {d:<3}|", end="")
    print("\n" + "-" * 60)

    for did in display_ids:
        print(f"{did:<6} |", end="")
        for day in range(1, TEST_DAYS + 1):
            val = results[did].get(day, ".")
            print(f" {val:<3}|", end="")
        print("")
    print("=" * 60)
    print("Легенда: '.' - пусто, '1'/'2' - смена, '!' - нарушение отдыха")


if __name__ == "__main__":
    main()