import sys
import os
import json
import glob
import re
import pandas as pd
from datetime import datetime, date
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# === НАСТРОЙКА ПУТЕЙ ===
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
os.chdir(project_root)

from src.config import (
    SELECTED_MONTH, SELECTED_YEAR, SELECTED_ROUTE, PROCESS_ALL_ROUTES,
    SIMULATION_MODE, SELECTED_PATTERN
)
from src.prepare_data.database import DataLoader
from src.logger import get_logger

logger = get_logger("SummaryReport")


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def prepare_absences_map(db_absences):
    absences_map = {}
    for item in db_absences:
        did = str(item["driver_id"])
        if did not in absences_map: absences_map[did] = {}
        current = item["from"]
        while current <= item["to"]:
            absences_map[did][current] = item["type"]
            current += pd.Timedelta(days=1).to_pytimedelta()
    return absences_map


def prepare_schedule_counts(db_schedules):
    counts = {}
    for schedule in db_schedules:
        if hasattr(schedule, 'model_dump'):
            s_dict = schedule.model_dump()
        elif hasattr(schedule, 'dict'):
            s_dict = schedule.dict()
        else:
            s_dict = schedule.__dict__

        r_num = str(s_dict.get("route_number") or s_dict.get("маршрут"))
        day_type = s_dict.get("day_type") or s_dict.get("день")
        trams = s_dict.get("trams") or s_dict.get("трамваи", [])

        shifts = 0
        for tram in trams:
            if hasattr(tram, 'model_dump'):
                t_dict = tram.model_dump()
            elif hasattr(tram, 'dict'):
                t_dict = tram.dict()
            elif isinstance(tram, dict):
                t_dict = tram
            else:
                t_dict = tram.__dict__

            if t_dict.get("смена_1") or t_dict.get("shift_1"): shifts += 1
            if t_dict.get("смена_2") or t_dict.get("shift_2"): shifts += 1

        if r_num not in counts: counts[r_num] = {'workday': 0, 'weekend': 0}

        if day_type == "рабочий":
            counts[r_num]['workday'] = shifts
        else:
            counts[r_num]['weekend'] = shifts
    return counts


def get_day_of_week_row(year, month, all_days):
    days_map = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    row = {"Маршрут": "", "Таб.№": "", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": "День недели"}
    for day in all_days:
        try:
            dt = date(year, month, day)
            row[day] = days_map[dt.weekday()]
        except:
            row[day] = "?"
    return row


def style_worksheet(ws, all_days_len):
    """Стилизация + Автоширина + Заморозка + Подсветка"""

    # (b) Закрепить первые 2 строки
    ws.freeze_panes = 'A3'

    fill_work = PatternFill("solid", fgColor="C6EFCE")  # Зеленый (Норма)
    fill_work_warn = PatternFill("solid", fgColor="FFEB9C")  # Желтый (Предупреждение)
    fill_work_weekend = PatternFill("solid", fgColor="FFC000")  # (g) Ярко-оранжевый (Выход в выходной)

    fill_reserve = PatternFill("solid", fgColor="FFC7CE")  # Красный (Резерв)
    fill_rest = PatternFill("solid", fgColor="F2F2F2")  # Серый (Выходной)
    fill_sick = PatternFill("solid", fgColor="FFFF00")  # Желтый (Больничный/Отпуск/Прочее)

    fill_header = PatternFill("solid", fgColor="4472C4")  # Синий заголовок
    fill_stat = PatternFill("solid", fgColor="D9E1F2")  # Голубой (Статистика)
    fill_guest_header = PatternFill("solid", fgColor="70AD47")  # Зеленый (Гости)
    fill_any_header = PatternFill("solid", fgColor="FFD966")  # Золотой (ANY)

    font_header = Font(bold=True, color="FFFFFF")
    font_bold = Font(bold=True)
    border = Border(left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin'))

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        first_val = str(row[0].value) if row[0].value else ""

        is_header_group = first_val in ["РАБОЧЕЕ ЯДРО"]
        is_guest_header = "ПРИВЛЕЧЕННЫЕ" in first_val or "РЕЗЕРВ (НЕ ЗАКРЕПЛЕННЫЕ)" in first_val
        is_any_header = "РЕЗЕРВ ANY" in first_val

        # (e) "Количество водителей, которым не хватило наряда" должно попадать сюда
        is_stat_block = any(k in first_val for k in [
            "Количество закрытых", "Количество незакрытых",
            "Количество смен", "Всего водителей",
            "Количество водителей"  # Ловит все строки начинающиеся так
        ])

        is_dow_row = str(row[-1].value) in ["Пн", "Вт", "Сб", "Вс"] or "День недели" in str(row[5].value)

        if is_header_group:
            for cell in row:
                cell.fill = fill_header
                cell.font = font_header
            continue

        if is_guest_header:
            for cell in row:
                cell.fill = fill_guest_header
                cell.font = font_header
            continue

        if is_any_header:
            for cell in row:
                cell.fill = fill_any_header
                cell.font = font_bold
            continue

        if is_stat_block:
            for cell in row:
                cell.fill = fill_stat
                cell.font = font_bold
                cell.border = border
            continue

        for cell in row:
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=False)
            val = str(cell.value) if cell.value else ""

            if is_dow_row:
                cell.font = font_bold
                if val in ["Сб", "Вс"]: cell.fill = PatternFill("solid", fgColor="E2EFDA")
                continue

            # Обработка значений ячеек

            # (g) Выход в выходной (метка [ВЫХ] ставится в process_route)
            if "[ВЫХ]" in val:
                cell.fill = fill_work_weekend
                # Убираем метку из видимого текста, чтобы было красиво
                cell.value = val.replace(" [ВЫХ]", "")

            elif "БОЛЬНИЧНЫЙ" in val or "ОТПУСК" in val or "ПРОЧЕЕ" in val:
                cell.fill = fill_sick

            elif "(!)" in val or "⚠️" in val:
                cell.fill = fill_work_warn

            elif "ч (" in val:
                cell.fill = fill_work

            # (f) В Strict режиме "РЕЗЕРВ" заменяется на "МАЛО ОТДЫХА", но красим так же
            elif "РЕЗЕРВ" in val or "МАЛО ОТДЫХА" in val:
                cell.fill = fill_reserve

            elif val in ["В", "B", "О", "Б"]:
                cell.fill = fill_rest

    # Автоподбор ширины
    for column_cells in ws.columns:
        length = 0
        for cell in column_cells:
            if cell.value:
                length = max(length, len(str(cell.value)))
        adjusted_width = (length + 2) * 1.05
        if adjusted_width > 55: adjusted_width = 55
        if adjusted_width < 5: adjusted_width = 5
        ws.column_dimensions[get_column_letter(column_cells[0].column)].width = adjusted_width


# === ЛОГИКА ОБРАБОТКИ ===

def get_schedule_from_driver(driver_obj):
    sch_type = "?"
    if hasattr(driver_obj, 'schedule_pattern'):
        sch_type = driver_obj.schedule_pattern
    elif hasattr(driver_obj, 'schedule'):
        sch_type = driver_obj.schedule
    if sch_type == "?" or sch_type is None:
        d_dump = driver_obj.model_dump() if hasattr(driver_obj, 'model_dump') else driver_obj.__dict__
        sch_type = d_dump.get('schedule') or d_dump.get('schedule_pattern') or d_dump.get('mode') or "?"
    return sch_type


# Хелпер для создания строк статистики
def create_stat_rows(stats_dict, total_drivers_count, all_days):
    rows = []

    def make_row(title, data_key):
        r = {"Маршрут": title, "Таб.№": "", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""}
        for d in all_days:
            # Берем значение из словаря, если ключа нет (например, stat_unclosed нет в daily_counters), считаем
            if data_key in stats_dict[d]:
                r[d] = stats_dict[d][data_key]
            elif data_key == 'unclosed':
                # Вычисляемое поле
                plan = stats_dict[d].get('plan_shifts', 0)
                closed = stats_dict[d].get('closed_shifts', 0)
                r[d] = max(0, plan - closed)
            else:
                r[d] = 0
        return r

    row_1 = make_row("Количество закрытых смен", 'closed_shifts')
    row_2 = make_row("Количество незакрытых смен", 'unclosed')
    row_3 = make_row("Количество смен по расписанию", 'plan_shifts')
    row_4 = make_row("Количество водителей, вышедших по расписанию на свой маршрут", 'drivers_native')
    row_5 = make_row("Количество водителей, вышедших по расписанию и не прикрепленных к маршруту", 'drivers_guest')
    row_6 = make_row("Количество водителей, вышедших на смену в выходной день", 'drivers_weekend_work')

    rows.extend([row_1, row_2, row_3, row_4, row_5, row_6])

    if SIMULATION_MODE == 'real':
        row_7 = make_row("Количество водителей, находящихся на выходном", 'drivers_on_rest')
        row_8 = make_row("Количество водителей, которым не хватило наряда", 'reserve_true')
        row_9 = {"Маршрут": "Всего водителей (закрепленных)", "Таб.№": total_drivers_count, "График": "", "Смен": "",
                 "Часов": "", "Резерв (дн)": ""}
        rows.extend([row_7, row_8, row_9])
    else:
        # STRICT mode
        row_7 = {"Маршрут": "Всего водителей (закрепленных)", "Таб.№": total_drivers_count, "График": "", "Смен": "",
                 "Часов": "", "Резерв (дн)": ""}
        rows.append(row_7)

    return rows


def process_route(route_number, sim_file_path, assigned_drivers, all_drivers_db, absences_map, schedule_counts,
                  month_num, all_days):
    """
    Возвращает расширенную статистику для режимов Real/Strict
    """
    try:
        with open(sim_file_path, "r", encoding="utf-8") as f:
            sim_data = json.load(f)
    except Exception:
        return [], [], [], [], {}, {}, {}

    native_drivers_map = {str(d.id): d for d in assigned_drivers}
    report_data_native = {did: {'days': {}, 'work_count': 0, 'reserve_count': 0, 'hours': 0} for did in
                          native_drivers_map}
    guest_drivers_data = {}

    daily_counters = {d: {
        'closed_shifts': 0, 'plan_shifts': 0,
        'drivers_native': 0, 'drivers_guest': 0,
        'drivers_weekend_work': 0, 'drivers_on_rest': 0,
        'reserve_true': 0
    } for d in all_days}

    route_plan = schedule_counts.get(str(route_number), {'workday': 0, 'weekend': 0})

    # 1. ФАКТ (Симуляция)
    for day_str, day_res in sim_data.items():
        if not day_str.isdigit(): continue
        day = int(day_str)

        dt = date(SELECTED_YEAR, month_num, day)
        is_weekend = dt.weekday() >= 5
        daily_counters[day]['plan_shifts'] = route_plan['weekend'] if is_weekend else route_plan['workday']

        for tram in day_res.get("roster", []):
            for shift_key in ["shift_1", "shift_2"]:
                s_info = tram.get(shift_key)
                if s_info and s_info.get("driver"):
                    daily_counters[day]['closed_shifts'] += 1

                    raw_did = s_info["driver"].split(" ")[0]
                    wh = s_info.get("work_hours", 8.0)
                    rest = s_info.get("rest_before", 0)
                    rest_str = "—" if rest > 500 else f"{rest:.0f}"
                    val = f"{wh:.1f}ч (отд {rest_str})"
                    if s_info.get("warnings"): val += " (!)"

                    # Определяем объект водителя
                    current_driver_obj = native_drivers_map.get(raw_did)
                    if not current_driver_obj:
                        current_driver_obj = next((d for d in all_drivers_db if str(d.id) == raw_did), None)

                    # (g) Подсветка работы в выходной (только для REAL)
                    if SIMULATION_MODE == 'real' and current_driver_obj:
                        status_in_plan = current_driver_obj.get_status_for_day(day)
                        # Если статус не "Работа" (1/2), а он работает -> Выходной
                        # Проверяем на В, О, Б или просто отсутствие явной смены
                        if status_in_plan in ['В', 'B', 'О', 'Б'] or status_in_plan not in ['1', '2']:
                            daily_counters[day]['drivers_weekend_work'] += 1
                            val += " [ВЫХ]"  # Метка для style_worksheet

                    if raw_did in report_data_native:
                        # СВОЙ
                        report_data_native[raw_did]['days'][day] = val
                        report_data_native[raw_did]['work_count'] += 1
                        report_data_native[raw_did]['hours'] += wh
                        daily_counters[day]['drivers_native'] += 1
                    else:
                        # ЧУЖОЙ
                        if raw_did not in guest_drivers_data:
                            if current_driver_obj:
                                guest_drivers_data[raw_did] = {'obj': current_driver_obj, 'days': {}, 'work_count': 0,
                                                               'hours': 0}
                        if raw_did in guest_drivers_data:
                            guest_drivers_data[raw_did]['days'][day] = val
                            guest_drivers_data[raw_did]['work_count'] += 1
                            guest_drivers_data[raw_did]['hours'] += wh
                        daily_counters[day]['drivers_guest'] += 1

    # 2. ЗАПОЛНЕНИЕ СТАТУСОВ
    for did, d_obj in native_drivers_map.items():
        driver_absences = absences_map.get(did, {})
        for day in all_days:
            if day in report_data_native[did]['days']: continue

            check_date = date(SELECTED_YEAR, month_num, day)
            if check_date in driver_absences:
                a_type = driver_absences[check_date]
                # (d) Добавлено ПРОЧЕЕ
                if a_type == "sick":
                    status = "БОЛЬНИЧНЫЙ"
                elif a_type == "vacation":
                    status = "ОТПУСК"
                else:
                    status = "ПРОЧЕЕ"

                report_data_native[did]['days'][day] = status
                continue

            plan = d_obj.get_status_for_day(day)
            if plan in ["1", "2"]:
                # (f) Strict -> МАЛО ОТДЫХА
                if SIMULATION_MODE == 'strict':
                    report_data_native[did]['days'][day] = "МАЛО ОТДЫХА"
                else:
                    report_data_native[did]['days'][day] = "РЕЗЕРВ"

                report_data_native[did]['reserve_count'] += 1
                daily_counters[day]['reserve_true'] += 1
            else:
                report_data_native[did]['days'][day] = plan
                if plan in ["В", "B", "О", "Б"]:
                    daily_counters[day]['drivers_on_rest'] += 1

    # 3. ФОРМИРОВАНИЕ СТРОК (СВОИ)
    active_rows = []
    reserve_rows = []
    sorted_native = sorted(report_data_native.keys(), key=lambda x: int(x) if x.isdigit() else x)
    for did in sorted_native:
        data = report_data_native[did]
        d_obj = native_drivers_map[did]
        row = {
            "Маршрут": route_number, "Таб.№": did, "График": get_schedule_from_driver(d_obj),
            "Смен": data['work_count'], "Часов": round(data['hours'], 1), "Резерв (дн)": data['reserve_count']
        }
        for day in all_days: row[day] = data['days'].get(day, "")
        if data['work_count'] > 0:
            active_rows.append(row)
        else:
            reserve_rows.append(row)

    # 4. ГОСТИ
    guest_rows = []
    sorted_guests = sorted(guest_drivers_data.keys(), key=lambda x: int(x) if x.isdigit() else x)
    for did in sorted_guests:
        g_data = guest_drivers_data[did]
        d_obj = g_data['obj']
        row = {
            "Маршрут": route_number, "Таб.№": f"{did} (Рез)", "График": get_schedule_from_driver(d_obj),
            "Смен": g_data['work_count'], "Часов": round(g_data['hours'], 1), "Резерв (дн)": ""
        }
        for day in all_days: row[day] = g_data['days'].get(day, "")
        guest_rows.append(row)

    # 5. ДАННЫЕ ДЛЯ ГЛОБАЛЬНОГО СВОДА
    guest_raw_global = {}
    any_drivers_raw_global = {}
    for did, g_data in guest_drivers_data.items():
        d_obj = g_data['obj']
        info = {'obj': g_data['obj'], 'updates': {}}
        for day, val in g_data['days'].items():
            info['updates'][day] = f"{val} №{route_number}"
        if str(d_obj.assigned_route_number).upper() == "ANY":
            any_drivers_raw_global[did] = info
        else:
            guest_raw_global[did] = info

    # 6. СТАТИСТИКА (Теперь полная и для листа маршрута!)
    # (a) Переносим новую статистику на листы маршрутов
    stats_block = create_stat_rows(daily_counters, len(native_drivers_map), all_days)

    daily_stats_detailed = daily_counters
    daily_stats_detailed['total_drivers_native'] = len(native_drivers_map)

    return active_rows, reserve_rows, guest_rows, stats_block, daily_stats_detailed, guest_raw_global, any_drivers_raw_global


# === MAIN ===

def main():
    logger.info("Инициализация генератора отчетов...")
    db = DataLoader()
    db.load_all()

    absences_map = prepare_absences_map(db.absences)
    schedule_counts = prepare_schedule_counts(db.schedules)

    month_map = {"Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6,
                 "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12}
    m_num = month_map.get(SELECTED_MONTH, 1)
    month_str_num = f"{m_num:02d}"

    # Пути с учетом подпапок режима
    results_dir = os.path.join(
        "env_synthetic", "data", "results", f"{SELECTED_PATTERN}",
        f"{month_str_num}_{SELECTED_MONTH}_{SELECTED_YEAR}",
        SIMULATION_MODE
    )
    search_pattern = os.path.join(results_dir, f"simulation_{SIMULATION_MODE}_*_{SELECTED_MONTH}_{SELECTED_YEAR}.json")

    found_files = glob.glob(search_pattern)

    if not found_files:
        logger.error(f"Файлы симуляции не найдены в {results_dir}")
        return

    with open(found_files[0], 'r') as f:
        tmp = json.load(f)
        all_days = sorted([int(k) for k in tmp.keys() if k.isdigit()])

    target_route = str(SELECTED_ROUTE) if not PROCESS_ALL_ROUTES else None

    if PROCESS_ALL_ROUTES:
        filename_summary = f"summary_report_{SIMULATION_MODE}_FULL_PARK_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"
    else:
        filename_summary = f"summary_report_{SIMULATION_MODE}_{SELECTED_ROUTE}_{SELECTED_MONTH}_{SELECTED_YEAR}.xlsx"

    directory_name = f"{month_str_num}_{SELECTED_MONTH}_{SELECTED_YEAR}"
    dynamic_summary_file = os.path.join("outputs", "SUMMARY_REPORTS", directory_name, SIMULATION_MODE, filename_summary)

    os.makedirs(os.path.dirname(dynamic_summary_file), exist_ok=True)
    writer = pd.ExcelWriter(dynamic_summary_file, engine='openpyxl')

    # Глобальные контейнеры
    global_natives = []
    global_reserves_native = []
    global_unassigned_guests = {}
    global_any_drivers = {}

    global_stats_detailed = {d: {
        'closed_shifts': 0, 'plan_shifts': 0,
        'drivers_native': 0, 'drivers_guest': 0,
        'drivers_weekend_work': 0, 'drivers_on_rest': 0,
        'reserve_true': 0
    } for d in all_days}
    global_total_drivers_count = 0

    dow_row = get_day_of_week_row(SELECTED_YEAR, m_num, all_days)

    def get_route_num(path):
        m = re.search(f"simulation_{SIMULATION_MODE}_(\\d+)_", os.path.basename(path))
        return int(m.group(1)) if m else 9999

    found_files.sort(key=get_route_num)
    processed_count = 0

    for file_path in found_files:
        route_num = str(get_route_num(file_path))
        if target_route and route_num != target_route: continue
        processed_count += 1

        route_assigned_drivers = [d for d in db.drivers if
                                  str(d.assigned_route_number) == route_num and d.month == SELECTED_MONTH]

        active, reserve, guests, stats, detailed_stats, guest_global_updates, any_drivers_updates = process_route(
            route_num, file_path, route_assigned_drivers, db.drivers, absences_map, schedule_counts, m_num, all_days
        )

        if PROCESS_ALL_ROUTES:
            global_natives.extend(active)
            global_reserves_native.extend(reserve)
            global_total_drivers_count += detailed_stats['total_drivers_native']

            for d in all_days:
                src = detailed_stats[d]
                dst = global_stats_detailed[d]
                for k in dst.keys():
                    dst[k] += src.get(k, 0)

            # Агрегация гостей
            for did, info in guest_global_updates.items():
                d_obj = info['obj']
                if not d_obj.assigned_route_number or d_obj.assigned_route_number == "0":
                    if did not in global_unassigned_guests:
                        global_unassigned_guests[did] = {'obj': d_obj, 'days': {}}
                    for day, val in info['updates'].items():
                        global_unassigned_guests[did]['days'][day] = val

            # Агрегация ANY
            for did, info in any_drivers_updates.items():
                d_obj = info['obj']
                if did not in global_any_drivers:
                    global_any_drivers[did] = {'obj': d_obj, 'days': {}}
                for day, val in info['updates'].items():
                    if day in global_any_drivers[did]['days']:
                        existing = global_any_drivers[did]['days'][day]
                        global_any_drivers[did]['days'][day] = f"КОНФЛИКТ: {existing} И {val}"
                    else:
                        global_any_drivers[did]['days'][day] = val

        # --- ЗАПИСЬ ЛИСТА МАРШРУТА ---
        sheet_rows = [dow_row]
        h_act = {"Таб.№": "РАБОЧЕЕ ЯДРО", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""}
        for d in all_days: h_act[d] = ""
        sheet_rows.append(h_act)
        for r in active: c = r.copy(); del c["Маршрут"]; sheet_rows.append(c)

        # (c) Убрали заголовок "ИЗБЫТОЧНЫЙ РЕЗЕРВ". Просто добавляем резервных.
        # Если нужно разделение пустой строкой, оставим sep.
        sep = {k: "" for k in h_act}
        if active and reserve:
            sheet_rows.append(sep)

        for r in reserve: c = r.copy(); del c["Маршрут"]; sheet_rows.append(c)

        if guests:
            sheet_rows.append(sep)
            h_guest = {"Таб.№": "ПРИВЛЕЧЕННЫЕ", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""}
            for d in all_days: h_guest[d] = ""
            sheet_rows.append(h_guest)
            for r in guests: c = r.copy(); del c["Маршрут"]; sheet_rows.append(c)

        # Статистика (a) теперь внизу (так как guests могут быть)
        sheet_rows.append(sep)
        for sr in stats:
            sr_c = sr.copy();
            title = sr_c["Маршрут"];
            del sr_c["Маршрут"]
            sr_c["Таб.№"] = title
            sheet_rows.append(sr_c)

        df = pd.DataFrame(sheet_rows)
        cols = ["Таб.№", "График", "Смен", "Часов", "Резерв (дн)"] + all_days
        df = df[cols]
        sn = f"Маршрут {route_num}"
        df.to_excel(writer, index=False, sheet_name=sn)
        style_worksheet(writer.sheets[sn], len(all_days))

    # --- ОБЩИЙ СВОД ---
    if PROCESS_ALL_ROUTES and processed_count > 0:
        logger.info("Формирование общего свода...")
        common_rows = [dow_row]
        sep = {k: "" for k in dow_row}

        # 1. Свои Активные
        h_glob = {"Маршрут": "РАБОЧЕЕ ЯДРО", "Таб.№": "", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""}
        for d in all_days: h_glob[d] = ""
        common_rows.append(h_glob)
        common_rows.extend(global_natives)

        # 2. Свои Резерв (c) Убрали заголовок "ИЗБЫТОЧНЫЙ РЕЗЕРВ"
        if global_natives and global_reserves_native:
            common_rows.append(sep)
        common_rows.extend(global_reserves_native)
        common_rows.append(sep)

        # 3. Резервные (незакрепленные) водители
        if global_unassigned_guests:
            h_unassigned = {"Маршрут": "РЕЗЕРВ (НЕ ЗАКРЕПЛЕННЫЕ)", "Таб.№": "", "График": "", "Смен": "", "Часов": "",
                            "Резерв (дн)": ""}
            for d in all_days: h_unassigned[d] = ""
            common_rows.append(h_unassigned)
            sorted_u = sorted(global_unassigned_guests.keys(), key=lambda x: int(x) if x.isdigit() else x)
            for did in sorted_u:
                info = global_unassigned_guests[did];
                d_obj = info['obj'];
                days_data = info['days']
                row = {"Маршрут": "Резерв", "Таб.№": did, "График": get_schedule_from_driver(d_obj),
                       "Смен": len(days_data), "Часов": "", "Резерв (дн)": ""}
                for day in all_days: row[day] = days_data.get(day, "")
                common_rows.append(row)
            common_rows.append(sep)

        # 4. Водители ANY (резервные)
        if global_any_drivers:
            h_any = {"Маршрут": "РЕЗЕРВ ANY (ВОДИТЕЛИ С МАРШРУТОМ ANY)", "Таб.№": "", "График": "", "Смен": "",
                     "Часов": "", "Резерв (дн)": ""}
            for d in all_days: h_any[d] = ""
            common_rows.append(h_any)
            sorted_any = sorted(global_any_drivers.keys(), key=lambda x: int(x) if x.isdigit() else x)
            for did in sorted_any:
                info = global_any_drivers[did];
                d_obj = info['obj'];
                days_data = info['days']
                total_hours = 0;
                work_days = 0;
                conflicts = 0;
                reserve_days = 0
                filled_days_data = {}
                for day in all_days:
                    if day in days_data:
                        day_val = days_data[day]
                        # (g) Подсветка и перенос маркера выходного дня
                        if "[ВЫХ]" in day_val:
                            filled_days_data[day] = day_val  # Оставляем маркер, style_worksheet его обработает
                        else:
                            filled_days_data[day] = day_val

                        if "КОНФЛИКТ" in day_val:
                            conflicts += 1
                        else:
                            work_days += 1
                            match = re.search(r'(\d+\.?\d*)ч', day_val)
                            if match: total_hours += float(match.group(1))
                    else:
                        check_date = date(SELECTED_YEAR, m_num, day)
                        driver_absences = absences_map.get(did, {})
                        if check_date in driver_absences:
                            a_type = driver_absences[check_date]
                            if a_type == "sick":
                                filled_days_data[day] = "БОЛЬНИЧНЫЙ"
                            elif a_type == "vacation":
                                filled_days_data[day] = "ОТПУСК"
                            else:
                                filled_days_data[day] = "ПРОЧЕЕ"
                        else:
                            plan = d_obj.get_status_for_day(day)
                            if plan in ["1", "2"]:
                                # (f) Strict logic
                                if SIMULATION_MODE == 'strict':
                                    filled_days_data[day] = "МАЛО ОТДЫХА"
                                else:
                                    filled_days_data[day] = "РЕЗЕРВ"
                                reserve_days += 1
                            else:
                                filled_days_data[day] = plan

                row = {
                    "Маршрут": "ANY", "Таб.№": f"{did}" + (" ⚠️" if conflicts > 0 else ""),
                    "График": get_schedule_from_driver(d_obj), "Смен": work_days,
                    "Часов": round(total_hours, 1) if total_hours > 0 else "",
                    "Резерв (дн)": reserve_days if reserve_days > 0 else (
                        f"Конфликтов: {conflicts}" if conflicts > 0 else "")
                }
                for day in all_days: row[day] = filled_days_data.get(day, "")
                common_rows.append(row)

            common_rows.append(sep)

        # 5. СТАТИСТИКА (В САМОМ НИЗУ, НИЖЕ ANY)
        logger.info(f"Формирование блока статистики для режима: {SIMULATION_MODE}")
        global_stats_rows = create_stat_rows(global_stats_detailed, global_total_drivers_count, all_days)
        common_rows.extend(global_stats_rows)

        df_glob = pd.DataFrame(common_rows)
        cols_glob = ["Маршрут", "Таб.№", "График", "Смен", "Часов", "Резерв (дн)"] + all_days
        df_glob = df_glob[cols_glob]

        df_glob.to_excel(writer, index=False, sheet_name="ОБЩИЙ СВОД")
        style_worksheet(writer.sheets["ОБЩИЙ СВОД"], len(all_days))

        wb = writer.book
        if "ОБЩИЙ СВОД" in wb.sheetnames:
            sheet = wb["ОБЩИЙ СВОД"]
            if sheet in wb._sheets:
                wb._sheets.remove(sheet)
            wb._sheets.insert(0, sheet)
            wb.active = 0

    writer.close()
    logger.info(f"Сводный отчет готов: {dynamic_summary_file}")


if __name__ == "__main__":
    main()