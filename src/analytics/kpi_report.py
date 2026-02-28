import os
import sys
import json
import glob
import pandas as pd
from datetime import datetime, date

# Настройка путей для импорта
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
os.chdir(project_root)

import src.config as config
from src.constants import get_month_number, MONTH_NAMES
from src.common_utils import get_month_sequence
from src.logger import get_logger

logger = get_logger("KPI_Report")


class KpiCollector:
    def __init__(self):
        self.stats = {}  # { "driver_id": { "cur_shifts": 0, "cur_hours": 0.0, "total_shifts": 0, "total_hours": 0.0 } }

    def get_period_list(self):
        """
        Возвращает список кортежей (MonthName, Year) для всего периода симуляции.
        """
        return list(get_month_sequence(
            config.SELECTED_MONTH,
            config.SELECTED_YEAR,
            config.SIMULATION_DURATION
        ))

    def find_simulation_file(self, month_name, year):
        """Ищет JSON с результатами для конкретного месяца"""
        m_num = get_month_number(month_name)
        folder_name = f"{m_num:02d}_{month_name}_{year}"

        # Базовый путь к результатам
        if config.USE_SYNTHETIC_DATA:
            base_results = os.path.join(config.DATA_DIR, "results", config.SELECTED_PATTERN)
        else:
            base_results = os.path.join(config.DATA_DIR, "results")

        target_dir = os.path.join(base_results, folder_name, config.SIMULATION_MODE)

        if not os.path.exists(target_dir):
            return None

        # Ищем файл. Шаблон: simulation_{mode}_*_{month}_{year}.json
        pattern = os.path.join(target_dir, f"simulation_{config.SIMULATION_MODE}_*_{month_name}_{year}.json")
        files = glob.glob(pattern)

        # Если файлов несколько (разные маршруты), нам нужно обработать их ВСЕ,
        # но для простоты предположим, что они могут быть склеены или мы берем первый попавшийся,
        # если логика позволяет.
        # В ВАШЕМ СЛУЧАЕ: У вас generate_daily_roster_for_all_routes сохраняет всё в один файл или по маршрутам?
        # Обычно это simulation_mode_route_...json.
        # Если мы хотим ВСЮ выработку водителя, нам нужно прочитать ВСЕ файлы маршрутов за этот месяц.

        return files

    def process_files(self, files, is_current_month):
        for filepath in files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Структура: { "1": { "roster": [...] }, "2": ... }
                for day_key, day_data in data.items():
                    if not isinstance(day_data, dict): continue

                    roster = day_data.get("roster", [])
                    for tram in roster:
                        for shift_key in ["shift_1", "shift_2"]:
                            shift = tram.get(shift_key)
                            if not shift or not shift.get("driver"):
                                continue

                            raw_did = shift["driver"].split(" ")[0]  # "101 (Вых!)" -> "101"
                            hours = shift.get("work_hours", 0.0)

                            # Инициализация
                            if raw_did not in self.stats:
                                self.stats[raw_did] = {
                                    "cur_shifts": 0, "cur_hours": 0.0,
                                    "total_shifts": 0, "total_hours": 0.0
                                }

                            # Накопление TOTAL (он включает в себя и current)
                            self.stats[raw_did]["total_shifts"] += 1
                            self.stats[raw_did]["total_hours"] += hours

                            # Накопление CURRENT
                            if is_current_month:
                                self.stats[raw_did]["cur_shifts"] += 1
                                self.stats[raw_did]["cur_hours"] += hours

            except Exception as e:
                logger.error(f"Ошибка чтения {filepath}: {e}")

    def run(self):
        periods = list(self.get_period_list())
        logger.info(f"Формирование KPI отчета за период: {periods}")

        for m_name, year in periods:
            is_current = (m_name == config.SELECTED_MONTH and year == config.SELECTED_YEAR)
            files = self.find_simulation_file(m_name, year)

            if not files:
                logger.warning(f"Данные за {m_name} {year} не найдены.")
                continue

            logger.info(f"Обработка {m_name} {year} (Файлов: {len(files)})... {'[TEKУЩИЙ]' if is_current else ''}")
            self.process_files(files, is_current)

        # Экспорт в Excel
        self.export_to_excel()

    def export_to_excel(self):
        if not self.stats:
            logger.warning("Нет данных для экспорта.")
            return

        # Преобразуем в список для DataFrame
        rows = []
        for did, data in self.stats.items():
            rows.append({
                "Таб. №": int(did) if did.isdigit() else did,
                "Смен (Тек. месяц)": data["cur_shifts"],
                "Часов (Тек. месяц)": round(data["cur_hours"], 2),
                "Смен (Всего)": data["total_shifts"],
                "Часов (Всего)": round(data["total_hours"], 2),
                # Доп. метрика: Среднее кол-во часов за период
                "Среднее (ч/мес)": round(data["total_hours"] / config.SIMULATION_DURATION, 2)
            })

        # Сортировка по ID
        rows.sort(key=lambda x: x["Таб. №"] if isinstance(x["Таб. №"], int) else 999999)

        df = pd.DataFrame(rows)

        # Путь сохранения
        m_num = get_month_number(config.SELECTED_MONTH)
        dir_name = f"{m_num:02d}_{config.SELECTED_MONTH}_{config.SELECTED_YEAR}"
        output_dir = os.path.join(config.ENV_DIR, "outputs", "KPI_REPORTS", dir_name)
        os.makedirs(output_dir, exist_ok=True)

        filename = f"KPI_Report_{config.SIMULATION_MODE}_{config.SELECTED_PATTERN}_{config.SELECTED_MONTH}_{config.SELECTED_YEAR}.xlsx"
        full_path = os.path.join(output_dir, filename)

        df.to_excel(full_path, index=False)
        logger.info(f"KPI Отчет успешно сохранен")

        # Вывод топ-5 и боттом-5 для быстрой проверки в консоли
        logger.info("КРАТКАЯ СВОДКА (ЛИДЕРЫ ПО ЧАСАМ)")
        top_5 = sorted(rows, key=lambda x: x["Часов (Всего)"], reverse=True)[:5]
        for r in top_5:
            logger.info(f"ID: {r['Таб. №']} | Total: {r['Часов (Всего)']}ч | Cur: {r['Часов (Тек. месяц)']}ч")

        logger.info("--- КРАТКАЯ СВОДКА (АУТСАЙДЕРЫ ПО ЧАСАМ) ---")
        bot_5 = sorted(rows, key=lambda x: x["Часов (Всего)"])[:5]
        for r in bot_5:
            logger.info(f"ID: {r['Таб. №']} | Total: {r['Часов (Всего)']}ч | Cur: {r['Часов (Тек. месяц)']}ч")


if __name__ == "__main__":
    reporter = KpiCollector()
    reporter.run()