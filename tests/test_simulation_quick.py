#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Быстрый тест симуляции (1 день, 1 маршрут).
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("=" * 60)
print("БЫСТРЫЙ ТЕСТ СИМУЛЯЦИИ")
print("=" * 60)

try:
    from src.prepare_data.database import DataLoader
    from src.core.scheduler import WorkforceAnalyzer
    import src.config as config
    
    print(f"\nРежим: {'SYNTHETIC' if config.USE_SYNTHETIC_DATA else 'REAL'}")
    print(f"Паттерн: {config.SELECTED_PATTERN}")
    
    print("\n" + "-" * 60)
    print("Загрузка данных...")
    print("-" * 60)
    
    db = DataLoader()
    db.load_all()
    
    print(f"\n✓ Загружено {len(db.drivers)} водителей")
    print(f"✓ Загружено {len(db.schedules)} расписаний")
    
    print("\n" + "-" * 60)
    print("Запуск симуляции (1 день, маршрут 47)...")
    print("-" * 60)
    
    analyzer = WorkforceAnalyzer(db)
    
    # Тестируем новый API
    result = analyzer.generate_daily_roster_for_all_routes(
        routes_list=["47"],
        day_of_month=1,
        target_month="Январь",
        target_year=2026,
        mode="strict"
    )
    
    if "47" in result:
        route_result = result["47"]
        if "error" in route_result:
            print(f"✗ Ошибка: {route_result['error']}")
        else:
            roster = route_result.get("roster", [])
            print(f"\n✓ Симуляция успешна!")
            print(f"  Дата: {route_result.get('date')}")
            print(f"  Маршрут: {route_result.get('route')}")
            print(f"  Вагонов в расписании: {len(roster)}")
            
            # Подсчет закрытых смен
            closed_shifts = 0
            for tram in roster:
                if tram.get("shift_1") and tram["shift_1"].get("driver"):
                    closed_shifts += 1
                if tram.get("shift_2") and tram["shift_2"].get("driver"):
                    closed_shifts += 1
            
            print(f"  Закрыто смен: {closed_shifts}")
            
            # Пример одного вагона
            if roster:
                print(f"\n  Пример (вагон {roster[0].get('tram_number')}):")
                s1 = roster[0].get("shift_1")
                if s1:
                    print(f"    Смена 1: водитель {s1.get('driver', 'НЕТ')}, {s1.get('work_hours', 0)}ч")
    
    print("\n✓ Тест симуляции завершен успешно!")
    
except Exception as e:
    print(f"\n✗ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
