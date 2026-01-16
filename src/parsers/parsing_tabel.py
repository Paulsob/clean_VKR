import json
import calendar
from pathlib import Path
from openpyxl import load_workbook

# --- Пути ---
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

TABELS_DIR = PROJECT_ROOT / "data" / "tabeles_2026"
OUTPUT_PATH = PROJECT_ROOT / "data" / "drivers.json"
YEAR = 2026

# Сопоставление английских названий месяцев → русские (для JSON)
MONTH_EN_TO_RU = {
    "january": "Январь",
    "february": "Февраль",
    "march": "Март",
    "april": "Апрель",
    "may": "Май",
    "june": "Июнь",
    "july": "Июль",
    "august": "Август",
    "september": "Сентябрь",
    "october": "Октябрь",
    "november": "Ноябрь",
    "december": "Декабрь",
}

# Порядок месяцев для сортировки
MONTH_ORDER = list(MONTH_EN_TO_RU.keys())

SHEET_NAME = "Sheet1"


def extract_month_from_filename(filename: str) -> str | None:
    """Извлекает название месяца из имени файла (например, 'january_2026.xlsx' → 'Январь')."""
    stem = filename.lower().replace(".xlsx", "")
    for en_month in MONTH_ORDER:
        if en_month in stem:
            return MONTH_EN_TO_RU[en_month]
    return None


def parse_whole_sheet(sheet_rows, month_name: str, year: int):
    """Парсит одну таблицу в структуру водителей."""
    # Получаем номер месяца
    month_num = list(MONTH_EN_TO_RU.values()).index(month_name) + 1
    days_in_month = calendar.monthrange(year, month_num)[1]

    if not sheet_rows:
        return []

    header = sheet_rows[0]
    total_columns_expected = len(header)
    drivers = []

    for row in sheet_rows[1:]:
        if len(row) < total_columns_expected:
            row = list(row) + [None] * (total_columns_expected - len(row))
        if len(row) < 5:
            continue

        try:
            tab_number = int(row[0])
        except (ValueError, TypeError):
            continue

        schedule = str(row[1]).strip() if row[1] is not None else ""
        mode = str(row[2]).strip() if row[2] is not None else ""

        day_values = row[5:]
        days = []
        for day in range(1, days_in_month + 1):
            idx = day - 1
            value = day_values[idx] if idx < len(day_values) else None
            value_str = str(value).strip() if value is not None else ""
            days.append({"day": day, "value": value_str})

        drivers.append({
            "tab_number": tab_number,
            "schedule": schedule,
            "mode": mode,
            "month": month_name,  # Добавляем месяц для контекста
            "days": days
        })

    return drivers


def main():
    all_drivers = []

    if not TABELS_DIR.exists():
        raise FileNotFoundError(f"Папка с табелями не найдена: {TABELS_DIR}")

    # Сортируем файлы по порядку месяцев
    files = sorted(
        TABELS_DIR.glob("*.xlsx"),
        key=lambda f: next(
            (i for i, m in enumerate(MONTH_ORDER) if m in f.name.lower()), 999
        )
    )

    for file_path in files:
        month_name = extract_month_from_filename(file_path.name)
        if not month_name:
            print(f"⚠️ Пропущен файл (не распознан месяц): {file_path.name}")
            continue

        print(f"Обрабатываю: {file_path.name} → {month_name} {YEAR}")

        try:
            workbook = load_workbook(file_path, data_only=True)
            if SHEET_NAME not in workbook.sheetnames:
                print(f"  ❌ Лист '{SHEET_NAME}' не найден в {file_path.name}")
                continue

            sheet = workbook[SHEET_NAME]
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]
            drivers = parse_whole_sheet(rows, month_name, YEAR)
            all_drivers.extend(drivers)

        except Exception as e:
            print(f"  ❌ Ошибка при обработке {file_path.name}: {e}")

    # Сохраняем результат
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "year": YEAR,
        "drivers": all_drivers
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Успешно обработано {len(all_drivers)} записей водителей.")
    print(f"Результат сохранён в: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()