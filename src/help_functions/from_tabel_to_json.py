import json
from pathlib import Path
import pandas as pd

MONTH = "Февраль"
YEAR = 2026
DAYS_IN_MONTH = 28

MAX_DRIVERS = 20

SHEET_NAME = "Весь_табель"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXCEL_PATH = PROJECT_ROOT / "data" / "data.xlsx"
OUTPUT_JSON = PROJECT_ROOT / "data" / "drivers.json"


def main():
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel файл не найден: {EXCEL_PATH}")

    df = pd.read_excel(
        EXCEL_PATH,
        sheet_name=SHEET_NAME,
        engine="openpyxl"
    )

    df = df.dropna(how="all")

    if MAX_DRIVERS is not None:
        df = df.head(MAX_DRIVERS)

    base_columns = ["Таб.№", "График", "Режим", "см.", "вых."]
    day_columns = [str(day) for day in range(1, DAYS_IN_MONTH + 1)]

    df = df[base_columns + day_columns]

    drivers = []

    for _, row in df.iterrows():
        driver = {
            "tab_number": row["Таб.№"],
            "schedule": row["График"],
            "mode": row["Режим"],
            "shift_start": row["см."],
            "shift_end": row["вых."],
            "days": []
        }

        for day in range(1, DAYS_IN_MONTH + 1):
            value = row[str(day)]
            driver["days"].append({
                "day": day,
                "value": None if pd.isna(value) else value
            })

        drivers.append(driver)

    result = {
        "month": MONTH,
        "year": YEAR,
        "days_in_month": DAYS_IN_MONTH,
        "drivers": drivers
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Табель на {MONTH} {YEAR} сохранён")
    print(f"Водителей в файле: {len(drivers)}")
    print(f"{OUTPUT_JSON}")


if __name__ == "__main__":
    main()
