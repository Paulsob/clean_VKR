from src.database import DataLoader
from src.scheduler import WorkforceAnalyzer


def main():
    # 1. Загрузка
    db = DataLoader()
    db.load_all()

    # 2. Анализ
    print("\n--- АНАЛИЗ ПОТРЕБНОСТИ В КАДРАХ ---")
    analyzer = WorkforceAnalyzer(db)

    print("\n--- ГЕНЕРАЦИЯ НАРЯДА НА 5-е ЧИСЛО ---")
    # Пытаемся закрыть Маршрут №1
    result = analyzer.generate_daily_roster(
        route_number=1,
        day_of_month=5,
        target_month="Январь"  # <-- Укажи то, что написано внутри JSON поля "month"
    )


    for tram in result["roster"]:
        print(f"Трамвай {tram['tram_number']}:")
        print(f"Утро: {tram['shift_1_driver'] or 'ПУСТО'}")
        print(f"Вечер: {tram['shift_2_driver'] or 'ПУСТО'}")


if __name__ == "__main__":
    main()
