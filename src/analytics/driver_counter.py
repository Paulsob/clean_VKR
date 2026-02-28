import os
import json
import sys
from typing import List, Set, Tuple

# Добавляем корневую директорию проекта в sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import src.config as config
from src.constants import get_month_number
from src.common_utils import get_month_sequence
from src.logger import get_logger

logger = get_logger("Analytics")


class DriverStatsCounter:
    def __init__(self):
        """
        Инициализация счетчика.
        Все параметры берутся из config.py, чтобы соответствовать текущему запуску симуляции.
        """
        self.pattern = config.SELECTED_PATTERN
        self.mode = config.SIMULATION_MODE
        self.default_start_month = config.SELECTED_MONTH
        self.default_start_year = config.SELECTED_YEAR
        self.default_duration = config.SIMULATION_DURATION

        # Определяем путь к папке с результатами
        if config.USE_SYNTHETIC_DATA:
            if self.pattern:
                self.base_results_dir = os.path.join(config.DATA_DIR, "results", self.pattern)
            else:
                self.base_results_dir = os.path.join(config.DATA_DIR, "results")
        else:
            self.base_results_dir = os.path.join(config.DATA_DIR, "results")

    def _get_month_sequence(self, start_month: str, start_year: int, duration: int) -> List[Tuple[str, int]]:
        """Генерирует последовательность (Месяц, Год)."""
        return get_month_sequence(start_month, start_year, duration)

    def count_unique_drivers(self,
                             start_month: str = None,
                             start_year: int = None,
                             duration_months: int = None,
                             routes: List[str] = None) -> int:

        s_month = start_month if start_month else self.default_start_month
        s_year = start_year if start_year else self.default_start_year
        dur = duration_months if duration_months else self.default_duration

        unique_drivers_ids = set()
        timeline = self._get_month_sequence(s_month, s_year, dur)

        logger.info(f"--- АНАЛИЗ ВОДИТЕЛЕЙ ({self.pattern} / {self.mode}) ---")
        logger.info(f"Папка поиска: {self.base_results_dir}")  # [ЛОГ ПУТИ]

        files_processed = 0

        for m_name, year in timeline:
            m_num = get_month_number(m_name)
            folder_name = f"{m_num:02d}_{m_name}_{year}"
            target_dir = os.path.join(self.base_results_dir, folder_name, self.mode)

            if not os.path.exists(target_dir):
                logger.warning(f"ПРОПУСК: Папка не найдена -> {target_dir}")
                continue

            # Определяем файлы для чтения
            files_to_read = []
            if routes:
                for r in routes:
                    fname = f"simulation_{self.mode}_{r}_{m_name}_{year}.json"
                    files_to_read.append(fname)
            else:
                try:
                    all_files = os.listdir(target_dir)
                    files_to_read = [
                        f for f in all_files
                        if f.startswith(f"simulation_{self.mode}") and f.endswith(".json")
                    ]
                except OSError:
                    continue

            # [ЛОГ] Печатаем первые 3 найденных файла, чтобы убедиться
            if files_to_read:
                logger.info(
                    f"В папке {folder_name} найдено {len(files_to_read)} файлов. Примеры: {files_to_read[:2]}...")
            else:
                logger.warning(f"В папке {folder_name} НЕТ файлов simulation_*.json!")

            for fname in files_to_read:
                full_path = os.path.join(target_dir, fname)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._extract_ids(data, unique_drivers_ids)
                        files_processed += 1
                except Exception as e:
                    logger.error(f"Ошибка чтения {fname}: {e}")

        logger.info(f"Обработано файлов: {files_processed}")
        logger.info(f"ФАКТИЧЕСКИ РАБОТАЛО: {len(unique_drivers_ids)} чел.")

        return len(unique_drivers_ids)

    def _extract_ids(self, json_data: dict, ids_set: set):
        """Парсит JSON и ищет driver_id."""
        for day_key, day_data in json_data.items():
            if not isinstance(day_data, dict): continue

            roster = day_data.get("roster", [])
            for tram in roster:
                for shift_key in ["shift_1", "shift_2"]:
                    shift_info = tram.get(shift_key)
                    if shift_info and isinstance(shift_info, dict):
                        # Берем ID водителя
                        drv_id = shift_info.get("driver")
                        # Дополнительная проверка на пустую строку
                        if drv_id and str(drv_id).strip():
                            ids_set.add(str(drv_id))


if __name__ == "__main__":
    # Инициализация (все настройки подтянутся из config.py)
    analyzer = DriverStatsCounter()

    # Запуск без параметров — использует настройки конфига (Январь, 2026, 12 месяцев и т.д.)
    print(f"\n>>> ЗАПУСК ПО КОНФИГУРАЦИИ <<<")
    total = analyzer.count_unique_drivers()
    print(f"Всего уникальных водителей за период симуляции: {total}")

    # Пример ручного запуска (если нужно проверить конкретный срез)
    # print("\n>>> ПРОВЕРКА ЗА 1 МЕСЯЦ <<<")
    # count_1 = analyzer.count_unique_drivers(duration_months=1)
    # print(f"За 1-й месяц работало: {count_1}")