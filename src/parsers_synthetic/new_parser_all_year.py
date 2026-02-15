import pandas as pd
import os
import calendar

# --- НАСТРОЙКА ПУТЕЙ ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))

INPUT_FILE = os.path.join(project_root, 'env_synthetic', 'data', 'Приложение №2 График 5х2.xlsx')
OUTPUT_DIR = os.path.join(project_root, 'env_synthetic', 'data', 'tabeles_2026_generated', '5x2')

YEAR = 2026


CYCLE_PATTERN = ['1', '1', '1', '1', '1', 'B', 'B', '2', '2', '2', '2', '2', 'B', 'B']
CYCLE_LEN = len(CYCLE_PATTERN)


def normalize_value(val):
    if pd.isna(val):
        return '?'
    val = str(val).strip().upper()
    # Обрабатываем все варианты выходных, которые могут встретиться
    if val in ['В', 'ВЫХ', 'V', 'B', '0']:
        return 'B'
    return val


MONTH_NAMES = {
    1: '01_january', 2: '02_february', 3: '03_march', 4: '04_april',
    5: '05_may', 6: '06_june', 7: '07_july', 8: '08_august',
    9: '09_september', 10: '10_october', 11: '11_november', 12: '12_december'
}


def find_cycle_offset(row_values, emp_info=""):
    # Очищаем данные
    valid_values = [normalize_value(x) for x in row_values if normalize_value(x) != '?']

    suffix_len = min(len(valid_values), 15)
    suffix = valid_values[-suffix_len:]

    if not suffix:
        print(f"  [DEBUG] У сотрудника {emp_info} нет данных в ячейках дат.")
        raise ValueError("Пустая строка")

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

    # Если цикл не найден, выводим что именно не совпало
    print(f"  [DEBUG] Не совпал график для: {emp_info}")
    print(f"          Что нашли в Excel: {suffix}")
    print(f"          Ожидаемый паттерн: {CYCLE_PATTERN}")
    raise ValueError("Логика не совпадает")


def apply_excel_formatting(writer, df, sheet_name):
    workbook = writer.book
    worksheet = workbook.add_worksheet(sheet_name)
    base_props = {'font_name': 'Verdana', 'font_size': 12, 'align': 'center', 'valign': 'vcenter', 'border': 1}
    fmt_base = workbook.add_format(base_props)
    fmt_header = workbook.add_format({**base_props, 'bold': True, 'bottom': 2})

    worksheet.set_column(0, 2, 10)
    worksheet.set_column(3, len(df.columns) - 1, 4)

    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, fmt_header)

    for row_idx, row in enumerate(df.values):
        for col_idx, value in enumerate(row):
            worksheet.write(row_idx + 1, col_idx, value, fmt_base)


def generate_schedules():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"--- ЗАПУСК ОТЛАДКИ ---")
    print(f"Файл: {INPUT_FILE}")

    if not os.path.exists(INPUT_FILE):
        print("!!! ОШИБКА: Файл не найден по указанному пути.")
        return

    df_input = pd.read_excel(INPUT_FILE)

    print(f"Все колонки файла: {list(df_input.columns)}")

    # Пытаемся найти начало дат
    if 'Смена' in df_input.columns:
        col_idx_start = list(df_input.columns).index('Смена') + 1
    else:
        # Если колонки 'Смена' нет, берем первые 3 колонки как метаданные
        col_idx_start = 3
        print(f"Предупреждение: Колонка 'Смена' не найдена. Метаданные = первые {col_idx_start} колонки.")

    day_columns = df_input.columns[col_idx_start:]
    meta_cols = list(df_input.columns[:col_idx_start])

    print(f"Колонки с метаданными: {meta_cols}")
    print(f"Первые 5 колонок с датами: {list(day_columns[:5])}")

    employee_states = {}
    for idx, row in df_input.iterrows():
        emp_name = str(row.iloc[0])  # Для лога берем значение из первой колонки
        try:
            days_values = row[day_columns].values
            last_day_cycle_index = find_cycle_offset(days_values, emp_info=emp_name)
            employee_states[idx] = last_day_cycle_index
        except ValueError:
            continue

    print(f"ИТОГО: Распознано {len(employee_states)} из {len(df_input)} строк.")

    if not employee_states:
        print("!!! ПРОГРАММА ОСТАНОВЛЕНА: Ни одна строка не подошла под CYCLE_PATTERN.")
        return

    # Подготовка и генерация
    DECEMBER_DAYS = 31
    current_states = {idx: (state + 1 + DECEMBER_DAYS) % CYCLE_LEN for idx, state in employee_states.items()}

    for month in range(1, 13):
        num_days = calendar.monthrange(YEAR, month)[1]
        file_name = f"{MONTH_NAMES[month]}_{YEAR}.xlsx"
        full_path = os.path.join(OUTPUT_DIR, file_name)

        new_data = []
        new_columns = meta_cols + list(range(1, num_days + 1))

        for idx, row in df_input.iterrows():
            if idx not in current_states: continue

            emp_meta = row[meta_cols].values.tolist()
            start_index = current_states[idx]
            month_schedule = []

            for d in range(num_days):
                cycle_idx = (start_index + d) % CYCLE_LEN
                val = CYCLE_PATTERN[cycle_idx]
                month_schedule.append('В' if val == 'B' else val)

            new_data.append(emp_meta + month_schedule)

        df_output = pd.DataFrame(new_data, columns=new_columns)
        with pd.ExcelWriter(full_path, engine='xlsxwriter') as writer:
            apply_excel_formatting(writer, df_output, 'Лист1')
        print(f"Сохранено: {file_name}")

    print("Работа завершена.")


if __name__ == "__main__":
    generate_schedules()
