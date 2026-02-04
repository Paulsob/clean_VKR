import pandas as pd
import numpy as np
import os
import sys
import calendar
from datetime import date, timedelta
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from src.logger import get_logger
from src.config import DATA_DIR, USE_SYNTHETIC_DATA

logger = get_logger(__name__)


# Логика выбора файлов в зависимости от режима
if USE_SYNTHETIC_DATA:
    # Список файлов для синтетики
    INPUT_FILES = [
        "Приложение №1 График 4х2.xlsx",
        "Приложение №2 График 5х2.xlsx",
        "Приложение №3 График 3х2х3х1.xlsx"
    ]
    # Папка для сохранения результатов (генерируем табели туда же, в data/tabeles_gen)
    OUTPUT_DIR = os.path.join(DATA_DIR, "tabeles_2026_generated")
else:
    # Один файл для реальных данных
    INPUT_FILES = ["tabeles_2026/02_february_2026.xlsx"]
    OUTPUT_DIR = os.path.join(DATA_DIR, "tabeles_2026")

# Константы смен
SHIFT_1 = 1
SHIFT_2 = 2
REST = 'В'

# Праздники 2026 (для 5х2)
HOLIDAYS_2026 = {
    (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9),
    (2, 23), (3, 8), (3, 9), (5, 1), (5, 9), (5, 11), (6, 12), (11, 4)
}

# Цикличные графики
CYCLIC_PATTERNS = {
    '4x2': [1, 1, 1, 1, 0, 0],
    '3x2x3x1': [1, 1, 1, 0, 0, 1, 1, 1, 0],
    '3x4': [1, 1, 1, 0, 0, 0, 0],
    '3x1x2x2': [1, 1, 1, 0, 1, 1, 0, 0],
    '1x6': [1, 0, 0, 0, 0, 0, 0]
}


# ================= ЛОГИКА ГРАФИКОВ =================

def normalize_key(s):
    if pd.isna(s): return ""
    s = str(s).lower().replace(' ', '').replace('*', 'x').replace('х', 'x')
    return s


def is_holiday(d):
    return (d.month, d.day) in HOLIDAYS_2026


def get_5x2_val_for_date(d, mode):
    if is_holiday(d) or d.weekday() >= 5:
        return REST
    norm_mode = normalize_key(mode)
    return SHIFT_2 if '2' in norm_mode and '1' not in norm_mode else SHIFT_1


def build_cycle_for_pattern(pattern_name, mode, mask):
    norm_mode = normalize_key(mode)
    if '1x2' in norm_mode and ('3x2x3x1' in pattern_name or '3x1x2x2' in pattern_name):
        blocks = []
        current_block = []
        for val in mask:
            if val == 1:
                current_block.append(val)
            else:
                if current_block:
                    blocks.append(current_block)
                    current_block = []
                blocks.append([0])
        if current_block: blocks.append(current_block)

        cycle = []
        shift_toggle = 2
        for block in blocks:
            for _ in block:
                cycle.append(shift_toggle if block[0] == 1 else REST)
            shift_toggle = 1 if shift_toggle == 2 else 2
        return cycle

    if '1x2' in norm_mode:
        part1 = [(SHIFT_1 if x else REST) for x in mask]
        part2 = [(SHIFT_2 if x else REST) for x in mask]
        return part1 + part2
    elif '2' in norm_mode:
        return [(SHIFT_2 if x else REST) for x in mask]
    else:
        return [(SHIFT_1 if x else REST) for x in mask]


def solve_cyclic(feb_vals, pattern_name, mode):
    pkey = normalize_key(pattern_name)
    mask = None
    for k, v in CYCLIC_PATTERNS.items():
        if normalize_key(k) == pkey:
            mask = v
            break
    if not mask: return None

    cycle = build_cycle_for_pattern(pattern_name, mode, mask)
    cycle_len = len(cycle)
    candidates = []

    for offset in range(cycle_len):
        score = 0
        mismatch = False
        for i, val in enumerate(feb_vals):
            # Если данных в таблице меньше, чем дней (например, короткий шаблон), не падаем
            if i >= len(feb_vals): break

            theo = cycle[(offset + i) % cycle_len]
            val_s = str(val).replace('.0', '')
            if val_s.lower() in ['b', 'v']: val_s = REST

            is_w_act = (val_s in ['1', '2'])
            is_w_theo = (str(theo) in ['1', '2'])

            if is_w_act != is_w_theo:
                mismatch = True
                break
            if val_s == str(theo): score += 1

        if not mismatch:
            candidates.append((score, offset))

    if not candidates: return None
    best_offset = max(candidates, key=lambda x: x[0])[1]

    jan1_offset = (best_offset - 31) % cycle_len
    full_seq = []
    for i in range(365):
        full_seq.append(cycle[(jan1_offset + i) % cycle_len])
    return full_seq


def solve_5x2(feb_vals, mode):
    full_seq = []
    start_date = date(2026, 1, 1)
    for i in range(365):
        curr_date = start_date + timedelta(days=i)
        val = get_5x2_val_for_date(curr_date, mode)
        full_seq.append(val)
    return full_seq


# ================= ЭКСПОРТ И ФОРМАТИРОВАНИЕ =================

def format_excel_file(filepath, month_num):
    wb = load_workbook(filepath)
    ws = wb.active
    font = Font(name='Verdana', size=12)
    holiday_fill = PatternFill(start_color="FFB7FD", end_color="FFB7FD", fill_type="solid")

    year = 2026
    _, days_in_month = calendar.monthrange(year, month_num)
    start_date = date(year, month_num, 1)

    col_names = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    try:
        col_vyh_index = col_names.index('вых.') + 1
    except ValueError:
        col_vyh_index = None

    for row_idx in range(2, ws.max_row + 1):
        if col_vyh_index:
            rest_count = 0
            for day_col in range(1, days_in_month + 1):
                day_col_letter = None
                for c in range(1, ws.max_column + 1):
                    if str(ws.cell(row=1, column=c).value) == str(day_col):
                        day_col_letter = c
                        break
                if day_col_letter:
                    val = str(ws.cell(row=row_idx, column=day_col_letter).value).strip()
                    if val == 'В': rest_count += 1
            ws.cell(row=row_idx, column=col_vyh_index, value=rest_count)

        for day_col in range(1, days_in_month + 1):
            col_letter = None
            for c in range(1, ws.max_column + 1):
                if str(ws.cell(row=1, column=c).value) == str(day_col):
                    col_letter = c
                    break
            if not col_letter: continue

            cell = ws.cell(row=row_idx, column=col_letter)
            cell.font = font
            cell.alignment = Alignment(horizontal='center')
            curr_date = start_date.replace(day=day_col)
            if curr_date.weekday() >= 5 or is_holiday(curr_date):
                cell.fill = holiday_fill

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length: max_length = len(str(cell.value))
            except:
                pass
        ws.column_dimensions[column].width = min(max_length + 2, 20)

    wb.save(filepath)


# ================= MAIN =================

def load_and_merge_inputs():
    """Загружает все входные файлы и объединяет их в один DataFrame"""
    merged_df = pd.DataFrame()

    for filename in INPUT_FILES:
        full_path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(full_path):
            logger.error(f"Файл не найден: {full_path}")
            continue

        logger.info(f"Загрузка файла: {filename}")
        try:
            df_part = pd.read_excel(full_path, dtype=str)
            merged_df = pd.concat([merged_df, df_part], ignore_index=True)
        except Exception as e:
            logger.error(f"Ошибка при чтении {filename}: {e}")

    return merged_df


def main():
    logger.info("Запуск генератора табелей")
    logger.info(f"Режим данных: {'SYNTHETIC' if USE_SYNTHETIC_DATA else 'REAL'}")

    # 1. Загружаем и склеиваем файлы
    df = load_and_merge_inputs()

    if df.empty:
        logger.error("Нет данных для обработки (пустой DataFrame).")
        return

    # 2. Нормализация колонок
    df.columns = [str(c).strip() for c in df.columns]

    day_cols = []
    # Ищем колонки дней (1..28)
    for i in range(1, 29):
        if str(i) in df.columns: day_cols.append(str(i))

    meta_cols = ['Таб.№', 'График', 'Режим', 'см.', 'вых.']
    for c in meta_cols:
        if c not in df.columns: df[c] = ""

    # 3. Генерация годового расписания
    full_year_map = {}
    stats_ok = 0

    for idx, row in df.iterrows():
        grafik = normalize_key(row['График'])
        mode = str(row['Режим'])

        # Собираем данные за февраль (или за кусок шаблона)
        feb_vals = []
        for d in day_cols:
            val = str(row[d]).strip()
            if val.lower() in ['b', 'v', 'nan']: val = REST
            feb_vals.append(val)

        # Пытаемся решить задачу
        result_seq = None
        if '5x2' in grafik:
            result_seq = solve_5x2(feb_vals, mode)
        else:
            result_seq = solve_cyclic(feb_vals, grafik, mode)

        if result_seq:
            full_year_map[idx] = result_seq
            stats_ok += 1
        else:
            logger.warning(f"Строка {idx} (Таб {row.get('Таб.№')}): Не удалось построить график {grafik}")
            full_year_map[idx] = [""] * 365

    logger.info(f"Успешно обработано водителей: {stats_ok}")

    # 4. Сохранение по месяцам
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

    months = [1] + list(range(3, 13))  # Январь + Март-Декабрь
    m_names = {1: 'january', 2: 'february', 3: 'march', 4: 'april', 5: 'may', 6: 'june',
               7: 'july', 8: 'august', 9: 'september', 10: 'october', 11: 'november', 12: 'december'}

    for m in months:
        fname = f"{m:02d}_{m_names[m]}_2026.xlsx"
        # Сохраняем всегда в OUTPUT_DIR (который настроен через config)
        out_path = os.path.join(OUTPUT_DIR, fname)

        logger.info(f"Генерация: {fname}")

        _, days_cnt = calendar.monthrange(2026, m)
        doy_start = date(2026, m, 1).timetuple().tm_yday - 1

        new_df = df[meta_cols].copy()

        for d in range(1, days_cnt + 1):
            vals = []
            d_idx = doy_start + (d - 1)
            for idx in df.index:
                # Если график не сгенерировался, будет пусто
                vals.append(full_year_map[idx][d_idx] if idx in full_year_map else "")
            new_df[str(d)] = vals

        new_df.to_excel(out_path, index=False)
        format_excel_file(out_path, m)

    logger.info("Готово! Проверьте папку " + OUTPUT_DIR)


if __name__ == "__main__":
    main()