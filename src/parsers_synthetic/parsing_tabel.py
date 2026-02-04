import pandas as pd
import os
import json
import sys

# --- Настройка путей и импорт ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
sys.path.append(project_root)

try:
    from src.utils import get_month_number
except ImportError:
    def get_month_number(month_name: str) -> int:
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        if month_name in months:
            return months.index(month_name) + 1
        raise ValueError(f"Unknown month: {month_name}")

# --- Константы ---
DATA_DIR = os.path.join(project_root, "env_synthetic", "data")
SOURCE_BASE = os.path.join(DATA_DIR, "tabeles_2026_generated")
JSON_BASE = os.path.join(DATA_DIR, "json_templates")
SUBFOLDERS = ["4x2", "5x2", "3x2x3x1"]

ENG_TO_RU_TITLE = {
    'january': 'Январь', 'february': 'Февраль', 'march': 'Март',
    'april': 'Апрель', 'may': 'Май', 'june': 'Июнь',
    'july': 'Июль', 'august': 'Август', 'september': 'Сентябрь',
    'october': 'Октябрь', 'november': 'Ноябрь', 'december': 'Декабрь'
}


def convert_xlsx_to_json():
    print("🚀 Конвертация в иерархический JSON формат...")

    for sub in SUBFOLDERS:
        source_dir = os.path.join(SOURCE_BASE, sub)
        target_dir = os.path.join(JSON_BASE, sub)

        if not os.path.exists(source_dir):
            continue

        os.makedirs(target_dir, exist_ok=True)

        for filename in os.listdir(source_dir):
            if filename.endswith(".xlsx"):
                parts = filename.split('_')
                if len(parts) < 2: continue

                month_eng = parts[1].lower()
                month_ru = ENG_TO_RU_TITLE.get(month_eng)

                try:
                    m_num = get_month_number(month_ru)
                    df = pd.read_excel(os.path.join(source_dir, filename), dtype=str)

                    # Инициализируем структуру по твоему формату
                    final_json = {
                        "month": month_ru,
                        "year": 2026,
                        "drivers": []
                    }

                    # Проходим по каждой строке (водителю)
                    for _, row in df.iterrows():
                        driver_entry = {
                            "tab_number": int(row.get('Таб. №', row.get('Таб.№', 0))),
                            "schedule": row.get('График', ''),
                            "mode": row.get('Смена', row.get('Режим', '')),
                            "days": []
                        }

                        # Собираем дни (только те колонки, которые являются числами)
                        for col in df.columns:
                            if col.isdigit():
                                driver_entry["days"].append({
                                    "day": int(col),
                                    "value": str(row[col])
                                })

                        final_json["drivers"].append(driver_entry)

                    # Сохранение
                    new_filename = f"{m_num:02d}_drivers_{month_eng}.json"
                    target_path = os.path.join(target_dir, new_filename)

                    with open(target_path, 'w', encoding='utf-8') as f:
                        json.dump(final_json, f, ensure_ascii=False, indent=4)

                    print(f"✅ Готово: {sub}/{new_filename}")

                except Exception as e:
                    print(f"⚠️ Ошибка в {filename}: {e}")


if __name__ == "__main__":
    convert_xlsx_to_json()