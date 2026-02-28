import pandas as pd
import os
import json
import sys

# --- Настройка путей ---
# Определяем корневую папку проекта относительно расположения скрипта
script_dir = os.path.dirname(os.path.abspath(__file__))
# Если скрипт лежит в корне или в subfolder, поднимаемся до корня проекта
# Предполагаем структуру: project/scripts/this_script.py -> project/
project_root = os.path.dirname(os.path.dirname(script_dir))
# Если путь определяется неправильно, можно задать жестко:
# project_root = r"C:\Users\psobo\PycharmProjects\clean_VKR-feature-synthetic-data-mode"

sys.path.append(project_root)


# --- Вспомогательная функция для номера месяца ---
def get_month_number(month_name: str) -> int:
    months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
              "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    # Приводим к единому регистру на всякий случай
    month_name = month_name.capitalize()
    if month_name in months:
        return months.index(month_name) + 1
    # Если вдруг передали на английском или с ошибкой
    raise ValueError(f"Unknown month: {month_name}")


# --- Константы ---
DATA_DIR = os.path.join(project_root, "env_synthetic", "data")
SOURCE_BASE = os.path.join(DATA_DIR, "tabeles_2026_generated")
JSON_BASE = os.path.join(DATA_DIR, "drivers_json")

# !!! ДОБАВИЛ НОВУЮ ПАПКУ В СПИСОК !!!
SUBFOLDERS = ["4x2", "5x2", "3x2x3x1", "5х2_holiday"]

ENG_TO_RU_TITLE = {
    'january': 'Январь', 'february': 'Февраль', 'march': 'Март',
    'april': 'Апрель', 'may': 'Май', 'june': 'Июнь',
    'july': 'Июль', 'august': 'Август', 'september': 'Сентябрь',
    'october': 'Октябрь', 'november': 'Ноябрь', 'december': 'Декабрь'
}


def convert_xlsx_to_json():
    print(f"🚀 Начинаем конвертацию. Источник: {SOURCE_BASE}")
    print(f"📂 Цель: {JSON_BASE}")

    for sub in SUBFOLDERS:
        source_dir = os.path.join(SOURCE_BASE, sub)
        target_dir = os.path.join(JSON_BASE, sub)

        if not os.path.exists(source_dir):
            print(f"⚠️ Папка не найдена, пропускаем: {source_dir}")
            continue

        # Создаем целевую папку (включая 5х2_holiday), если её нет
        os.makedirs(target_dir, exist_ok=True)
        print(f"--- Обработка папки: {sub} ---")

        files = [f for f in os.listdir(source_dir) if f.endswith(".xlsx") and not f.startswith("~$")]

        if not files:
            print(f"   (пусто) Нет xlsx файлов.")
            continue

        for filename in files:
            # Ожидаем формат имени: 01_january_2026.xlsx
            parts = filename.replace('.xlsx', '').split('_')

            # Проверка формата имени файла
            if len(parts) < 2:
                print(f"   ⏩ Пропуск файла с неверным форматом имени: {filename}")
                continue

            month_eng = parts[1].lower()
            month_ru = ENG_TO_RU_TITLE.get(month_eng)

            if not month_ru:
                print(f"   ⏩ Не удалось определить месяц из имени файла: {filename}")
                continue

            try:
                m_num = get_month_number(month_ru)

                # Читаем Excel
                file_path = os.path.join(source_dir, filename)
                df = pd.read_excel(file_path, dtype=str)

                # Структура JSON
                final_json = {
                    "month": month_ru,
                    "year": 2026,
                    "drivers": []
                }

                # Парсинг строк
                for _, row in df.iterrows():
                    # Безопасное получение данных с вариантами названий колонок
                    tab_num = row.get('Таб. №', row.get('Таб.№', row.get('Tab_No', '0')))
                    schedule = row.get('График', row.get('Schedule', ''))
                    mode = row.get('Смена', row.get('Режим', row.get('Mode', '')))

                    driver_entry = {
                        "tab_number": int(float(tab_num)) if str(tab_num).replace('.', '', 1).isdigit() else 0,
                        "schedule": str(schedule),
                        "mode": str(mode),
                        "days": []
                    }

                    # Перебор колонок для поиска дней (1, 2, 3...)
                    for col in df.columns:
                        col_str = str(col).strip()

                        # Если название колонки - число (день месяца)
                        if col_str.isdigit():
                            val = str(row[col])
                            # Очистка NaN и float (например 1.0 -> 1)
                            if val == 'nan': val = ""
                            if val.endswith('.0'): val = val[:-2]

                            driver_entry["days"].append({
                                "day": int(col_str),
                                "value": val
                            })

                    final_json["drivers"].append(driver_entry)

                # Сохранение JSON
                # Формат имени выходного файла: 01_drivers_january.json
                new_filename = f"{m_num:02d}_drivers_{month_eng}.json"
                target_path = os.path.join(target_dir, new_filename)

                with open(target_path, 'w', encoding='utf-8') as f:
                    json.dump(final_json, f, ensure_ascii=False, indent=4)

                print(f"   ✅ Конвертирован: {filename} -> {new_filename}")

            except Exception as e:
                print(f"   ❌ Ошибка при обработке {filename}: {e}")
                # import traceback
                # traceback.print_exc()



if __name__ == "__main__":
    convert_xlsx_to_json()