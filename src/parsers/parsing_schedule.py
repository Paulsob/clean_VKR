import pandas as pd
import re
import json
import os

os.makedirs("../../data", exist_ok=True)
output_path = "../../data/schedule.json"
file_path = "../../data/data.xlsx"

sheet_names = pd.ExcelFile(file_path).sheet_names[2:]
all_schedules = []


def is_valid_time(value):
    """Проверяет, является ли значение корректным временем (а не числом вроде 8,3)"""
    if pd.isna(value):
        return False
    if hasattr(value, 'strftime'):  # datetime.time, Timestamp
        return True
    s = str(value).strip()
    if ':' in s:
        parts = s.split(':')
        if len(parts) == 2:
            try:
                h = int(parts[0])
                m = int(re.split(r'\D', parts[1])[0])  # берём только цифры до не-цифры
                return 0 <= h <= 23 and 0 <= m <= 59
            except:
                return False
    return False


def format_time(value):
    if pd.isna(value):
        return None
    if hasattr(value, 'strftime'):
        return value.strftime("%H:%M")
    s = str(value).strip()
    if ':' in s:
        parts = s.split(':')
        hour = parts[0].zfill(2)
        minute_part = re.split(r'\D', parts[1])[0]  # "07 AM" → "07"
        minute = minute_part.zfill(2)[:2]
        return f"{hour}:{minute}"
    return None


for sheet_name in sheet_names:
    print(f"Обработка листа: {sheet_name}")

    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None, engine='openpyxl')
    df.iloc[:, 0] = df.iloc[:, 0].ffill()  # заполняем объединённые ячейки

    # Определяем тип дня
    if "рабочего" in sheet_name.lower():
        day_type = "рабочий"
    elif "выходного" in sheet_name.lower():
        day_type = "выходной"
    else:
        continue

    # Ищем номер маршрута
    route_number = None
    for i in range(4):
        if pd.notna(df.iloc[i, 0]):
            cell_val = str(df.iloc[i, 0])
            if "маршрут" in cell_val.lower():
                match = re.search(r'(\d+)', cell_val)
                if match:
                    route_number = int(match.group(1))
                    break
    if route_number is None:
        continue

    trams = []
    for idx in range(4, len(df)):
        cell_A = df.iloc[idx, 0]
        if pd.isna(cell_A):
            break

        cell_A_str = str(cell_A).strip()
        if not cell_A_str:
            continue

        # Проверяем: есть ли хотя бы одна цифра? (чтобы исключить случайные пустые строки)
        if not re.search(r'\d', cell_A_str):
            continue

        # Извлекаем времена
        dep1 = df.iloc[idx, 5]
        arr1 = df.iloc[idx, 6]
        dep2 = df.iloc[idx, 10]
        arr2 = df.iloc[idx, 11]

        # Ключевая проверка: есть ли хотя бы одно корректное время?
        if not any(is_valid_time(t) for t in [dep1, arr1, dep2, arr2]):
            continue  # пропускаем строки с "7,8", "9,2" и т.п.

        tram = {
            "номер": cell_A_str,  # сохраняем как строку: "1", "2Ш", "10Б"
            "смена_1": {
                "отправление": format_time(dep1),
                "прибытие": format_time(arr1)
            },
            "смена_2": {
                "отправление": format_time(dep2),
                "прибытие": format_time(arr2)
            }
        }
        trams.append(tram)

    if trams:
        all_schedules.append({
            "маршрут": route_number,
            "день": day_type,
            "трамваи": trams
        })

# Сохраняем
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(all_schedules, f, ensure_ascii=False, indent=2)

print(f"\n✅ Успешно сохранено {len(all_schedules)} расписаний в {output_path}")