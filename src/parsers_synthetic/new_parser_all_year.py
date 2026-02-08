import pandas as pd
import os
import calendar
import sys

# --- НАСТРОЙКА ПУТЕЙ ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))

INPUT_FILE = os.path.join(project_root, 'env_synthetic', 'data', 'Приложение №1 График 4х2.xlsx')
OUTPUT_DIR = os.path.join(project_root, 'env_synthetic', 'data', 'tabeles_2026_generated', '4x2')

YEAR = 2026

# --- ЛОГИКА ГРАФИКА ---
CYCLE_PATTERN = ['1', '1', '1', '1', 'B', 'B', '2', '2', '2', '2', 'B', 'B']
CYCLE_LEN = len(CYCLE_PATTERN)

MONTH_NAMES = {
    1: '01_january', 2: '02_february', 3: '03_march', 4: '04_april',
    5: '05_may', 6: '06_june', 7: '07_july', 8: '08_august',
    9: '09_september', 10: '10_october', 11: '11_november', 12: '12_december'
}


def normalize_value(val):
    if pd.isna(val):
        return '?'
    val = str(val).strip().upper()
    if val == 'В':
        return 'B'
    return val


def find_cycle_offset(row_values):
    valid_values = [normalize_value(x) for x in row_values if not pd.isna(x)]
    suffix_len = min(len(valid_values), 15)
    suffix = valid_values[-suffix_len:]

    if not suffix:
        raise ValueError("Пустая строка данных")

    for i in range(CYCLE_LEN):
        match = True
        for k in range(suffix_len):
            val_in_row = suffix[-(k + 1)]
            target_cycle_idx = (i - k) % CYCLE_LEN
            expected_val = CYCLE_PATTERN[target_cycle_idx]

            if val_in_row != expected_val:
                match = False
                break
        if match:
            return i

    raise ValueError(f"Не удалось определить логику: {suffix}")


def apply_excel_formatting(writer, df, sheet_name):
    """
    Создает лист, применяет стили Verdana 12, границы и ширину столбцов,
    и записывает данные вручную.
    """
    workbook = writer.book
    # ЯВНО СОЗДАЕМ ЛИСТ
    worksheet = workbook.add_worksheet(sheet_name)

    # --- ОПРЕДЕЛЕНИЕ СТИЛЕЙ ---

    # Базовый стиль: Verdana 12, по центру, тонкие границы
    base_props = {
        'font_name': 'Verdana',
        'font_size': 12,
        'align': 'center',
        'valign': 'vcenter',
        'border': 1
    }

    fmt_base = workbook.add_format(base_props)

    # Стиль для каждого 12-го сотрудника (жирная линия снизу)
    fmt_thick_bottom = workbook.add_format({**base_props, 'bottom': 2})  # 2 = Thick border

    # Стиль заголовка (жирный шрифт + жирная линия снизу)
    fmt_header = workbook.add_format({
        'font_name': 'Verdana',
        'font_size': 12,
        'bold': True,
        'align': 'center',
        'valign': 'vcenter',
        'border': 1,
        'bottom': 2
    })

    # --- ПРИМЕНЕНИЕ ШИРИНЫ СТОЛБЦОВ ---

    # Первые 3 столбца (метаданные) пошире (ширина ~10 символов)
    worksheet.set_column(0, 2, 10)
    # Столбцы с днями (с 4-го и до конца) поуже (ширина ~4 символа)
    worksheet.set_column(3, len(df.columns) - 1, 4)

    # --- ЗАПИСЬ ДАННЫХ ---

    # 1. Пишем заголовки
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, fmt_header)

    # 2. Пишем тело таблицы
    for row_idx, row in enumerate(df.values):
        # Логика: каждый 12-й сотрудник получает жирную черту снизу.
        # В Excel это строки данных. Сотрудник 1 (idx 0), Сотрудник 12 (idx 11).
        # (row_idx + 1) % 12 == 0

        current_fmt = fmt_base
        if (row_idx + 1) % 12 == 0:
            current_fmt = fmt_thick_bottom

        for col_idx, value in enumerate(row):
            # +1 к row_idx, т.к. 0-я строка занята шапкой
            worksheet.write(row_idx + 1, col_idx, value, current_fmt)


def generate_schedules():
    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
            print(f"Создана папка: {OUTPUT_DIR}")
        except OSError as e:
            print(f"ОШИБКА создания папки: {e}")
            return

    print(f"Чтение файла: {INPUT_FILE}")
    if not os.path.exists(INPUT_FILE):
        print("ОШИБКА: Файл не найден.")
        return

    try:
        # Читаем Excel. По умолчанию читает первый лист.
        df_input = pd.read_excel(INPUT_FILE)
    except Exception as e:
        print(f"ОШИБКА чтения Excel: {e}")
        return

    # Определение колонок
    try:
        if 'Смена' in df_input.columns:
            col_idx_start = list(df_input.columns).index('Смена') + 1
            day_columns = df_input.columns[col_idx_start:]
            meta_cols = list(df_input.columns[:col_idx_start])
        else:
            meta_cols = df_input.columns[:3].tolist()
            day_columns = df_input.columns[3:]
    except Exception:
        print("Ошибка структуры файла")
        return

    # Анализ состояний
    employee_states = {}
    print("Анализ графиков...")
    for idx, row in df_input.iterrows():
        try:
            days_values = row[day_columns].values
            last_day_cycle_index = find_cycle_offset(days_values)
            employee_states[idx] = last_day_cycle_index
        except ValueError:
            continue

    print(f"Распознано {len(employee_states)} сотрудников.")

    # Подготовка к генерации
    DECEMBER_DAYS = 31
    current_states = {}

    for idx, state_nov30 in employee_states.items():
        state_jan1 = (state_nov30 + 1 + DECEMBER_DAYS) % CYCLE_LEN
        current_states[idx] = state_jan1

    # Генерация файлов
    for month in range(1, 13):
        num_days = calendar.monthrange(YEAR, month)[1]
        month_name = MONTH_NAMES[month]
        file_name = f"{month_name}_{YEAR}.xlsx"
        full_path = os.path.join(OUTPUT_DIR, file_name)

        new_data = []
        new_columns = meta_cols + [i for i in range(1, num_days + 1)]

        for idx, row in df_input.iterrows():
            if idx not in current_states:
                continue

            emp_meta = row[meta_cols].values.tolist()
            start_index = current_states[idx]
            month_schedule = []

            for d in range(num_days):
                cycle_idx = (start_index + d) % CYCLE_LEN
                val = CYCLE_PATTERN[cycle_idx]
                if val == 'B': val = 'В'
                month_schedule.append(val)

            new_data.append(emp_meta + month_schedule)

        df_output = pd.DataFrame(new_data, columns=new_columns)

        # Сохранение с форматированием
        try:
            # Называем лист 'Лист1', как в исходнике
            with pd.ExcelWriter(full_path, engine='xlsxwriter') as writer:
                apply_excel_formatting(writer, df_output, 'Лист1')
            print(f"Сгенерирован: {file_name}")
        except Exception as e:
            print(f"Ошибка записи {file_name}: {e}")
            import traceback
            traceback.print_exc()

        for idx in current_states:
            current_states[idx] = (current_states[idx] + num_days) % CYCLE_LEN

    print("Работа завершена.")


if __name__ == "__main__":
    generate_schedules()