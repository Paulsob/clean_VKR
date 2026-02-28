#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест загрузки данных с новой системой валидации.
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("=" * 60)
print("ТЕСТ ЗАГРУЗКИ ДАННЫХ С ВАЛИДАЦИЕЙ")
print("=" * 60)

try:
    from src.prepare_data.database import DataLoader
    import src.config as config
    
    print(f"\nРежим: {'SYNTHETIC' if config.USE_SYNTHETIC_DATA else 'REAL'}")
    print(f"Паттерн: {config.SELECTED_PATTERN}")
    print(f"Месяц: {config.SELECTED_MONTH} {config.SELECTED_YEAR}")
    print(f"Директория данных: {config.DATA_DIR}")
    
    print("\n" + "-" * 60)
    print("Начинаем загрузку данных...")
    print("-" * 60)
    
    db = DataLoader()
    db.load_all()
    
    print("\n" + "=" * 60)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 60)
    print(f"Водители: {len(db.drivers)}")
    print(f"Расписания: {len(db.schedules)}")
    print(f"Закрепления: {len(db.assignments)}")
    print(f"Отсутствия: {len(db.absences)}")
    print(f"Нормы рассчитаны для: {len(db.driver_norms)} водителей")
    
    if db.drivers:
        print(f"\nПример водителя:")
        driver = db.drivers[0]
        print(f"  ID: {driver.id}")
        print(f"  График: {driver.schedule_pattern}")
        print(f"  Месяц: {driver.month}")
        print(f"  Закреплен за маршрутом: {driver.assigned_route_number}")
        if str(driver.id) in db.driver_norms:
            print(f"  Норма часов: {db.driver_norms[str(driver.id)]}")
    
    print("\n✓ Загрузка данных завершена успешно!")
    
except Exception as e:
    print(f"\n✗ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
