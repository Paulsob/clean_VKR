from src.database import DataLoader
from src.scheduler import WorkforceAnalyzer


def main():
    # 1. Загрузка данных
    db = DataLoader()
    db.load_all()

    # 2. Настройки расчета
    selected_route = "47"
    selected_day = 1
    selected_month = "Январь"
    selected_year = 2026

    analyzer = WorkforceAnalyzer(db)

    print(f"\n--- ГЕНЕРАЦИЯ НАРЯДА: {selected_day} {selected_month} {selected_year} ---")

    result = analyzer.generate_daily_roster(
        route_number=selected_route,
        day_of_month=selected_day,
        target_month=selected_month,
        target_year=selected_year
    )

    if "error" in result:
        print(f"⛔ ОШИБКА ГЕНЕРАЦИИ: {result['error']}")
    else:
        print("\n" + "="*60)
        print(f"📄 РЕЗУЛЬТАТ: Маршрут №{selected_route}")
        print(f"📅 Дата: {result['date']} {selected_month} {selected_year}")
        print(f"🗓  День: {result['day_name']} ({result['day_type']})")
        print("="*60 + "\n")

        for tram in result["roster"]:
            # Формируем строку вывода
            u_driver = tram['shift_1_driver'] or '❌ ПУСТО'
            v_driver = tram['shift_2_driver'] or '❌ ПУСТО'

            print(f"Вагон {tram['tram_number']}:")
            print(f"  🌞 Утро : {u_driver}")
            print(f"  🌜 Вечер: {v_driver}")

            # Если есть проблемы (например, не нашли водителя)
            if tram['issues']:
                for issue in tram['issues']:
                    print(f"     ⚠️ {issue}")

        print("-" * 30)
        print(f"Резерв (водители, оставшиеся без смены): {len(result['drivers_leftover'])} чел.")
        if result['drivers_leftover']:
            print(f"ID резерва: {', '.join(result['drivers_leftover'])}")


if __name__ == "__main__":
    main()