import sys
import os
import json
import glob
import re
import pandas as pd
from datetime import date
from openpyxl.styles import PatternFill, Alignment, Border, Side, Font

# === НАСТРОЙКИ ПУТЕЙ ===
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
os.chdir(project_root)

from src.config import (
    SELECTED_ROUTE, SELECTED_MONTH, SELECTED_YEAR, SIMULATION_MODE,
    PROCESS_ALL_ROUTES, OUTPUTS_DIR
)
from src.logger import get_logger
from src.prepare_data.database import DataLoader

logger = get_logger("ScheduleBook")

MONTH_TO_NUM = {
    "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6,
    "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12,
}

DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
HEADER_ROW_IDX = 6


def get_day_of_week(year, month_num, day):
    try:
        dt = date(year, month_num, day)
        return DAYS_RU[dt.weekday()]
    except:
        return "?"


def process_single_route_json(json_path, route_num, all_drivers_db, month_num):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {json_path}: {e}")
        return []

    days_sorted = sorted([k for k in data.keys() if k.isdigit()], key=int)
    rows = []
    drivers_map = {str(d.id): d for d in all_drivers_db}

    for day_str in days_sorted:
        day_res = data[day_str]
        roster = day_res.get("roster", [])
        day_int = int(day_str)
        dow = get_day_of_week(SELECTED_YEAR, month_num, day_int)

        try:
            roster.sort(key=lambda x: int(x.get("tram_number", 0)))
        except:
            pass

        for tram in roster:
            t_num = tram.get("tram_number", "?")

            def process_shift(shift_data):
                # 1. ОКНО В РАСПИСАНИИ (Смены просто не существует в плане)
                if not shift_data:
                    return "", "", False

                d_name = shift_data.get("driver_name", "")
                t_range = shift_data.get("time_range", "")

                # 2. СРЫВ (Смена в плане есть, но водитель не назначен)
                # Проверяем: либо имя пустое, либо явно написано "НЕТ ВОДИТЕЛЯ",
                # либо в данных есть время, но нет ID водителя.
                is_no_driver = not d_name or d_name == "НЕТ ВОДИТЕЛЯ" or not shift_data.get("driver")

                if is_no_driver:
                    # Если есть время, но нет водителя — красим в красный
                    # Если нет даже времени — обычно это тоже считается срывом, если объект смены создан
                    return "[FAIL]", t_range, False

                # 3. ВОДИТЕЛЬ НАЗНАЧЕН (Логика без изменений)
                d_raw_id = shift_data.get("driver", "").split(" ")[0]
                has_warn = bool(shift_data.get("warnings"))
                is_weekend_work = False

                if SIMULATION_MODE == 'real':
                    d_obj = drivers_map.get(d_raw_id)
                    if d_obj:
                        status = d_obj.get_status_for_day(day_int)
                        if status not in ['1', '2']:
                            is_weekend_work = True

                warn_mark = " (!)" if has_warn else ""
                weekend_mark = " [ВЫХ]" if is_weekend_work else ""

                final_name = f"{d_name}{warn_mark}{weekend_mark}"
                return final_name, t_range, has_warn

            # Получаем данные
            d1, t1, w1 = process_shift(tram.get("shift_1"))
            d2, t2, w2 = process_shift(tram.get("shift_2"))

            rows.append({
                "Дата": f"{day_int:02d}.{month_num:02d} ({dow})",
                "Вагон": int(t_num) if str(t_num).isdigit() else t_num,
                "I Смена (Водитель)": d1,
                "I Время": t1,
                "II Смена (Водитель)": d2,
                "II Время": t2,
                "Проблемы": ", ".join(tram.get("issues", [])),
                "_day_int": day_int
            })
    return rows


def add_legend(ws):
    fill_success = PatternFill("solid", fgColor="C6EFCE")
    fill_fail = PatternFill("solid", fgColor="FF5555")  # Ярко-красный
    fill_warn = PatternFill("solid", fgColor="FFEB9C")
    fill_weekend = PatternFill("solid", fgColor="FFC000")
    font_bold = Font(bold=True)

    ws['A1'] = "ЛЕГЕНДА:"
    ws['A1'].font = font_bold

    ws['A2'] = "Смена закрыта (OK)"
    ws['A2'].fill = fill_success
    ws['A2'].alignment = Alignment(horizontal='center')

    ws['B2'] = "Срыв (Нет водителя)"
    ws['B2'].fill = fill_fail
    ws['B2'].alignment = Alignment(horizontal='center')
    ws.column_dimensions['B'].width = 20

    ws['A3'] = "Нарушение / Конфликт (!)"
    ws['A3'].fill = fill_warn
    ws['A3'].alignment = Alignment(horizontal='center')

    ws['A4'] = "Пустая белая ячейка = Смены нет в расписании"
    ws['A4'].font = Font(italic=True, size=9)

    if SIMULATION_MODE == 'real':
        ws['B3'] = "Работа в выходной день"
        ws['B3'].fill = fill_weekend
        ws['B3'].alignment = Alignment(horizontal='center')


def style_worksheet(ws):
    fill_header = PatternFill("solid", fgColor="4F81BD")
    fill_success = PatternFill("solid", fgColor="C6EFCE")  # Зеленый
    fill_fail = PatternFill("solid", fgColor="FF5555")  # Красный
    fill_warn = PatternFill("solid", fgColor="FFEB9C")  # Желтый
    fill_weekend = PatternFill("solid", fgColor="FFC000")  # Оранжевый

    font_header = Font(bold=True, color="FFFFFF")

    border = Border(left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin'))
    thick_bottom = Border(left=Side(style='thin'), right=Side(style='thin'),
                          top=Side(style='thin'), bottom=Side(style='thick'))

    # Шапка
    for cell in ws[HEADER_ROW_IDX]:
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal='center')

    # Определение границ дней (для жирной линии внизу дня)
    day_end_rows = []
    current_day = None
    data_start = HEADER_ROW_IDX + 1

    for row in ws.iter_rows(min_row=data_start, max_row=ws.max_row, min_col=1, max_col=1):
        val = row[0].value
        if current_day is None:
            current_day = val
        elif val != current_day:
            day_end_rows.append(row[0].row - 1)
            current_day = val
    day_end_rows.append(ws.max_row)

    # Основной цикл по строкам данных
    for row in ws.iter_rows(min_row=data_start, max_row=ws.max_row):
        is_day_end = row[0].row in day_end_rows
        current_border = thick_bottom if is_day_end else border

        # 1. Сначала применяем базовые стили (границы и выравнивание)
        for cell in row:
            cell.border = current_border
            cell.alignment = Alignment(horizontal='center', vertical='center')

        # 2. Получаем текст из колонки "Проблемы" (Индекс 6 / Колонка G)
        issues_text = str(row[6].value) if row[6].value else ""

        # 3. Обработка колонок водителей (C=индекс 2, E=индекс 4)
        for idx in [2, 4]:
            cell = row[idx]
            val = str(cell.value) if cell.value else ""

            # --- НОВАЯ ЛОГИКА ПО ТЕКСТУ ИЗ "ПРОБЛЕМЫ" ---
            if idx == 2 and "Нет водителя (1)" in issues_text:
                cell.fill = fill_fail
            elif idx == 4 and "Нет водителя (2)" in issues_text:
                cell.fill = fill_fail

            # --- СТАНДАРТНАЯ ЛОГИКА ---
            elif "[FAIL]" in val:
                cell.fill = fill_fail
                cell.value = ""  # Очищаем метку, оставляя цвет
            elif "[ВЫХ]" in val:
                cell.fill = fill_weekend
                cell.value = val.replace(" [ВЫХ]", "")
            elif "(!)" in val:
                cell.fill = fill_warn
            elif val and val.strip() != "":
                # Если ячейка не пустая и не попала под условия выше — значит всё ОК (зеленый)
                cell.fill = fill_success

    # Закрепление области
    freeze_cell = f'A{HEADER_ROW_IDX + 1}'
    ws.freeze_panes = freeze_cell

    # Настройка ширины колонок
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 25
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 50


def main():
    logger.info("Начинаем генерацию журнала нарядов...")

    db = DataLoader()
    db.load_all()

    m_num = MONTH_TO_NUM.get(SELECTED_MONTH, 1)
    month_str = f"{m_num:02d}"

    base_results_dir = os.path.join(
        "data", "results",
        f"{month_str}_{SELECTED_MONTH}_{SELECTED_YEAR}",
        SIMULATION_MODE
    )
    search_pattern = os.path.join(base_results_dir,
                                  f"simulation_{SIMULATION_MODE}_*_{SELECTED_MONTH}_{SELECTED_YEAR}.json")
    found_files = glob.glob(search_pattern)

    if not found_files:
        logger.error(f"Файлы не найдены: {base_results_dir}")
        return

    files_to_process = []

    def get_route_from_filename(path):
        m = re.search(f"simulation_{SIMULATION_MODE}_(\\d+)_", os.path.basename(path))
        return m.group(1) if m else "Unknown"

    target_route = str(SELECTED_ROUTE) if not PROCESS_ALL_ROUTES else None

    for fp in found_files:
        r_num = get_route_from_filename(fp)
        if target_route and r_num != target_route: continue
        files_to_process.append((r_num, fp))

    files_to_process.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 9999)

    if PROCESS_ALL_ROUTES:
        out_filename = f"schedule_book_{SIMULATION_MODE}_FULL_PARK_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
    else:
        out_filename = f"schedule_book_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"

    out_path = os.path.join(
        OUTPUTS_DIR, "SCHEDULE_BOOKS",
        f"{month_str}_{SELECTED_MONTH}_{SELECTED_YEAR}",
        SIMULATION_MODE,
        out_filename
    )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    writer = pd.ExcelWriter(out_path, engine='openpyxl')

    for r_num, f_path in files_to_process:
        logger.info(f"Обработка маршрута {r_num}...")
        rows = process_single_route_json(f_path, r_num, db.drivers, m_num)

        if not rows: continue

        df = pd.DataFrame(rows)
        df_clean = df.drop(columns=["_day_int"])

        sheet_name = f"Маршрут {r_num}"
        df_clean.to_excel(writer, index=False, sheet_name=sheet_name, startrow=HEADER_ROW_IDX - 1)

        ws = writer.sheets[sheet_name]
        add_legend(ws)
        style_worksheet(ws)

    try:
        writer.close()
        logger.info(f"Распределение готово: {out_path}")
    except Exception as e:
        logger.error(f"Ошибка сохранения Excel: {e}")


if __name__ == "__main__":
    main()