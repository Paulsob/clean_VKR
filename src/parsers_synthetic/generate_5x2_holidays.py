import pandas as pd
import os
import datetime
import calendar

# --- 1. Настройки ---
OUTPUT_PATH = r"C:\Users\psobo\PycharmProjects\clean_VKR-feature-synthetic-data-mode\env_synthetic\data\tabeles_2026_generated\5х2_holiday"
YEAR = 2026
EMPLOYEES_COUNT = 700

# Создаем папку
os.makedirs(OUTPUT_PATH, exist_ok=True)

# --- 2. Логика праздников ---
# Базовые праздники (месяц, день)
base_holidays = [
    (2, 23), (3, 8), (5, 1), (5, 9), (6, 12), (11, 4)
]

holiday_dates = set()

# 2.1. Особая логика для Января (жестко задаем 1-9 января)
# 12 января не трогаем, оно останется рабочим, так как не входит в этот список
for d in range(1, 10):
    holiday_dates.add(datetime.date(YEAR, 1, d))

# 2.2. Остальные праздники с логикой переноса
for month, day in base_holidays:
    dt = datetime.date(YEAR, month, day)
    holiday_dates.add(dt)

    # Если праздник выпадает на Сб(5) или Вс(6), переносим на Пн
    if dt.weekday() >= 5:
        next_day = dt + datetime.timedelta(days=1)
        # Ищем первый рабочий день
        while next_day.weekday() != 0 or next_day in holiday_dates:
            next_day += datetime.timedelta(days=1)
        holiday_dates.add(next_day)

month_names = {
    1: "january", 2: "february", 3: "march", 4: "april",
    5: "may", 6: "june", 7: "july", 8: "august",
    9: "september", 10: "october", 11: "november", 12: "december"
}


def get_day_value(current_date, emp_id):
    """
    Определяет значение ячейки (В, 1, 2)
    emp_id нужен для балансировки смен (чет/нечет)
    """
    # 1. Проверка на выходные и праздники
    if current_date.weekday() >= 5 or current_date in holiday_dates:
        return "В"

    # 2. Определение смены
    # Получаем номер недели (ISO). 1 января 2026 - это 1-я неделя.
    week_num = current_date.isocalendar()[1]

    # Логика:
    # Четные сотрудники (2, 4...): Неделя 1 -> Смена 1. (Нечетная неделя -> 1, Четная -> 2)
    # Нечетные сотрудники (1, 3...): Неделя 1 -> Смена 2. (Нечетная неделя -> 2, Четная -> 1)

    is_employee_even = (emp_id % 2 == 0)
    is_week_odd = (week_num % 2 != 0)

    if is_employee_even:
        # Четный сотрудник начинает с 1
        return 1 if is_week_odd else 2
    else:
        # Нечетный сотрудник начинает с 2
        return 2 if is_week_odd else 1


# --- 3. Генерация файлов ---
print(f"Путь сохранения: {OUTPUT_PATH}")

for month in range(1, 13):
    _, num_days = calendar.monthrange(YEAR, month)
    file_name = f"{month:02d}_{month_names[month]}_{YEAR}.xlsx"
    full_path = os.path.join(OUTPUT_PATH, file_name)

    # Генерируем заголовки
    days_columns = [i for i in range(1, num_days + 1)]
    columns = ['Таб. №', 'График', 'Смена'] + days_columns

    # Оптимизация: вычисляем два паттерна графика на месяц (для четных и нечетных ID)
    # Это быстрее, чем вызывать функцию для каждой ячейки (700 * 30 раз)
    schedule_pattern_even_id = []  # Для сотрудников 2, 4...
    schedule_pattern_odd_id = []  # Для сотрудников 1, 3...

    for day in range(1, num_days + 1):
        d_obj = datetime.date(YEAR, month, day)
        # Для паттернов берем условные ID: 2 (четный) и 1 (нечетный)
        schedule_pattern_even_id.append(get_day_value(d_obj, 2))
        schedule_pattern_odd_id.append(get_day_value(d_obj, 1))

    data = []
    for emp_id in range(1, EMPLOYEES_COUNT + 1):
        row = {
            'Таб. №': emp_id,
            'График': '5х2',
            'Смена': '1х2'
        }

        # Выбираем нужный паттерн
        if emp_id % 2 == 0:
            current_schedule = schedule_pattern_even_id
        else:
            current_schedule = schedule_pattern_odd_id

        # Заполняем дни
        for day_idx, val in enumerate(current_schedule):
            row[day_idx + 1] = val

        data.append(row)

    df = pd.DataFrame(data, columns=columns)

    # --- Сохранение и стилизация ---
    try:
        with pd.ExcelWriter(full_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')

            workbook = writer.book
            worksheet = writer.sheets['Sheet1']

            # Стиль ячеек: Verdana 12, по центру
            cell_format = workbook.add_format({
                'font_name': 'Verdana',
                'font_size': 12,
                'align': 'center',
                'valign': 'vcenter'
            })

            # Стиль заголовка: жирный, границы
            header_format = workbook.add_format({
                'font_name': 'Verdana',
                'font_size': 12,
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })

            # Настройка ширины столбцов
            worksheet.set_column(0, 0, 10, cell_format)  # Таб. №
            worksheet.set_column(1, 2, 8, cell_format)  # График, Смена

            # Столбцы дней (D...) узкие
            last_col_idx = 3 + num_days - 1
            worksheet.set_column(3, last_col_idx, 4, cell_format)

            # Применяем стиль заголовков
            for col_num, value in enumerate(df.columns):
                worksheet.write(0, col_num, value, header_format)

        print(f"[OK] {file_name}")

    except Exception as e:
        print(f"[ERROR] {file_name}: {e}")

print("Готово!")