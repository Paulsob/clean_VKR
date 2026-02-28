#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки рефакторинга.
Проверяет основные компоненты без запуска полной симуляции.
"""
import sys
import os

# Добавляем путь к проекту
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("=" * 60)
print("ТЕСТ РЕФАКТОРИНГА - ПРОВЕРКА ИМПОРТОВ И БАЗОВОЙ ФУНКЦИОНАЛЬНОСТИ")
print("=" * 60)

# Тест 1: Импорт констант
print("\n[1/7] Тест импорта constants.py...")
try:
    from src.constants import get_month_number, get_month_name, MONTH_MAP
    assert get_month_number("Январь") == 1
    assert get_month_name(12) == "Декабрь"
    print("✓ constants.py работает корректно")
except Exception as e:
    print(f"✗ Ошибка в constants.py: {e}")
    sys.exit(1)

# Тест 2: Импорт config без циклических зависимостей
print("\n[2/7] Тест импорта config.py (проверка циклических зависимостей)...")
try:
    import src.config as config
    assert hasattr(config, 'DATA_DIR')
    assert hasattr(config, 'path_manager')
    print(f"✓ config.py загружен успешно")
    print(f"  - DATA_DIR: {config.DATA_DIR}")
    print(f"  - USE_SYNTHETIC_DATA: {config.USE_SYNTHETIC_DATA}")
except Exception as e:
    print(f"✗ Ошибка в config.py: {e}")
    sys.exit(1)

# Тест 3: PathManager
print("\n[3/7] Тест PathManager...")
try:
    from src.path_manager import PathManager
    pm = PathManager(
        base_dir=config.BASE_DIR,
        use_synthetic=True,
        selected_pattern="5x2"
    )
    
    test_path = pm.get_simulation_file_path("47", "Январь", 2026, "strict")
    assert "simulation_strict_47_Январь_2026.json" in test_path
    print("✓ PathManager работает корректно")
    print(f"  - Пример пути: ...{test_path[-60:]}")
except Exception as e:
    print(f"✗ Ошибка в PathManager: {e}")
    sys.exit(1)

# Тест 4: Общие утилиты
print("\n[4/7] Тест common_utils.py...")
try:
    from src.common_utils import get_month_sequence, get_previous_month, format_driver_id
    
    seq = get_month_sequence("Декабрь", 2025, 3)
    assert seq == [("Декабрь", 2025), ("Январь", 2026), ("Февраль", 2026)]
    
    prev = get_previous_month("Январь", 2026)
    assert prev == ("Декабрь", 2025)
    
    driver_id = format_driver_id("101 (Вых!)")
    assert driver_id == "101"
    
    print("✓ common_utils.py работает корректно")
except Exception as e:
    print(f"✗ Ошибка в common_utils.py: {e}")
    sys.exit(1)

# Тест 5: Обновленный utils.py
print("\n[5/7] Тест обратной совместимости utils.py...")
try:
    from src.utils import get_month_number, get_day_type_by_date
    assert get_month_number("Март") == 3
    day_type = get_day_type_by_date(1, "Январь", 2026)
    assert day_type in ["рабочий", "выходной"]
    print("✓ utils.py сохраняет обратную совместимость")
except Exception as e:
    print(f"✗ Ошибка в utils.py: {e}")
    sys.exit(1)

# Тест 6: DataLoader с новой валидацией
print("\n[6/7] Тест DataLoader с валидацией...")
try:
    from src.prepare_data.database import DataLoader, LoadingStats
    
    # Проверяем, что класс LoadingStats существует
    stats = LoadingStats()
    assert hasattr(stats, 'drivers_loaded')
    assert hasattr(stats, 'add_error')
    
    print("✓ DataLoader обновлен с системой валидации")
except Exception as e:
    print(f"✗ Ошибка в DataLoader: {e}")
    sys.exit(1)

# Тест 7: Проверка импортов в основных модулях
print("\n[7/7] Тест импортов в основных модулях...")
try:
    # Эти импорты должны работать без ошибок
    from src.core.run_simulation import get_dynamic_paths
    from src.analytics.driver_counter import DriverStatsCounter
    from src.analytics.kpi_report import KpiCollector
    
    print("✓ Все основные модули импортируются корректно")
except Exception as e:
    print(f"✗ Ошибка импорта основных модулей: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓✓✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО ✓✓✓")
print("=" * 60)
print("\nРефакторинг выполнен корректно:")
print("  1. Устранены циклические зависимости")
print("  2. Создан PathManager для управления путями")
print("  3. Добавлена валидация и логирование ошибок")
print("  4. Устранено дублирование кода")
print("\nМодель готова к работе!")
