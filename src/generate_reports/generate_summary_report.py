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
    SUMMARY_REPORT_FILE
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
    """Стилизация + Автоширина + Запрет переноса"""
    fill_work = PatternFill("solid", fgColor="C6EFCE")
    fill_work_warn = PatternFill("solid", fgColor="FFEB9C")
    fill_reserve = PatternFill("solid", fgColor="FFC7CE")
    fill_rest = PatternFill("solid", fgColor="F2F2F2")
    fill_sick = PatternFill("solid", fgColor="FFFF00")
    fill_header = PatternFill("solid", fgColor="4472C4")
    fill_stat = PatternFill("solid", fgColor="D9E1F2")
    fill_guest_header = PatternFill("solid", fgColor="70AD47")  # Зеленый для заголовка гостей

    font_header = Font(bold=True, color="FFFFFF")
    font_bold = Font(bold=True)
    border = Border(left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin'))

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        first_val = str(row[0].value) if row[0].value else ""

        is_header_group = first_val in ["РАБОЧЕЕ ЯДРО", "ИЗБЫТОЧНЫЙ РЕЗЕРВ"]
        is_guest_header = "ПРИВЛЕЧЕННЫЕ" in first_val or "РЕЗЕРВ (НЕ ЗАКРЕПЛЕННЫЕ)" in first_val
        is_stat_block = ("Количество" in first_val) or ("Всего водителей" in first_val)
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

            if "БОЛЬНИЧНЫЙ" in val or "ОТПУСК" in val:
                cell.fill = fill_sick
            elif "(!)" in val:
                cell.fill = fill_work_warn
            elif "ч (" in val:
                cell.fill = fill_work
            elif "РЕЗЕРВ" in val:
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
        if adjusted_width > 45: adjusted_width = 45
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


def process_route(route_number, sim_file_path, assigned_drivers, all_drivers_db, absences_map, schedule_counts,
                  month_num, all_days):
    """
    Возвращает: active_rows, reserve_rows, guest_rows, stats, guest_raw_data_for_global
    """
    try:
        with open(sim_file_path, "r", encoding="utf-8") as f:
            sim_data = json.load(f)
    except Exception:
        return [], [], [], [], {}, {}

    # Разделяем водителей на Своих и Гостей
    # Свои - это assigned_drivers (мы их знаем)
    native_drivers_map = {str(d.id): d for d in assigned_drivers}

    # Данные для отчета
    report_data_native = {did: {'days': {}, 'work_count': 0, 'reserve_count': 0, 'hours': 0} for did in
                          native_drivers_map}

    # Гости: { did: { 'obj': driver_obj, 'days': { day: "val" } } }
    guest_drivers_data = {}

    # Статистика (только по своим!)
    stat_active = {d: 0 for d in all_days}
    stat_reserve_true = {d: 0 for d in all_days}

    # 1. ФАКТ (Симуляция)
    for day_str, day_res in sim_data.items():
        if not day_str.isdigit(): continue
        day = int(day_str)

        for tram in day_res.get("roster", []):
            for shift_key in ["shift_1", "shift_2"]:
                s_info = tram.get(shift_key)
                if s_info and s_info.get("driver"):
                    raw_did = s_info["driver"].split(" ")[0]

                    wh = s_info.get("work_hours", 8.0)
                    rest = s_info.get("rest_before", 0)
                    rest_str = "—" if rest > 500 else f"{rest:.0f}"
                    val = f"{wh:.1f}ч (отд {rest_str})"
                    if s_info.get("warnings"): val += " (!)"

                    # Проверяем, свой или чужой
                    if raw_did in report_data_native:
                        # СВОЙ
                        report_data_native[raw_did]['days'][day] = val
                        report_data_native[raw_did]['work_count'] += 1
                        report_data_native[raw_did]['hours'] += wh
                        stat_active[day] += 1  # В статистику идут только свои (по условию задачи)
                    else:
                        # ЧУЖОЙ (Привлеченный)
                        if raw_did not in guest_drivers_data:
                            # Ищем в базе
                            d_obj = next((d for d in all_drivers_db if str(d.id) == raw_did), None)
                            if d_obj:
                                guest_drivers_data[raw_did] = {'obj': d_obj, 'days': {}, 'work_count': 0, 'hours': 0}

                        if raw_did in guest_drivers_data:
                            guest_drivers_data[raw_did]['days'][day] = val
                            guest_drivers_data[raw_did]['work_count'] += 1
                            guest_drivers_data[raw_did]['hours'] += wh
                            # В статистику НЕ включаем по просьбе пользователя

    # 2. ЗАПОЛНЕНИЕ СТАТУСОВ (Только для СВОИХ)
    for did, d_obj in native_drivers_map.items():
        driver_absences = absences_map.get(did, {})
        for day in all_days:
            if day in report_data_native[did]['days']: continue

            check_date = date(SELECTED_YEAR, month_num, day)
            if check_date in driver_absences:
                a_type = driver_absences[check_date]
                report_data_native[did]['days'][day] = "БОЛЬНИЧНЫЙ" if a_type == "sick" else "ОТПУСК"
                continue

            plan = d_obj.get_status_for_day(day)
            if plan in ["1", "2"]:
                report_data_native[did]['days'][day] = "РЕЗЕРВ"
                report_data_native[did]['reserve_count'] += 1
                stat_reserve_true[day] += 1
            else:
                report_data_native[did]['days'][day] = plan

    # 3. ФОРМИРОВАНИЕ СТРОК (СВОИ)
    active_rows = []
    reserve_rows = []

    sorted_native = sorted(report_data_native.keys(), key=lambda x: int(x) if x.isdigit() else x)
    for did in sorted_native:
        data = report_data_native[did]
        d_obj = native_drivers_map[did]
        row = {
            "Маршрут": route_number,
            "Таб.№": did,
            "График": get_schedule_from_driver(d_obj),
            "Смен": data['work_count'],
            "Часов": round(data['hours'], 1),
            "Резерв (дн)": data['reserve_count']
        }
        for day in all_days: row[day] = data['days'].get(day, "")

        if data['work_count'] > 0:
            active_rows.append(row)
        else:
            reserve_rows.append(row)

    # 4. ФОРМИРОВАНИЕ СТРОК (ГОСТИ) - ДЛЯ ЛИСТА МАРШРУТА
    # Здесь мы просто выводим их работу. Пустые дни = пустота.
    guest_rows = []
    sorted_guests = sorted(guest_drivers_data.keys(), key=lambda x: int(x) if x.isdigit() else x)

    for did in sorted_guests:
        g_data = guest_drivers_data[did]
        d_obj = g_data['obj']
        row = {
            "Маршрут": route_number,
            "Таб.№": f"{did} (Рез)",  # Пометка для локального отчета
            "График": get_schedule_from_driver(d_obj),
            "Смен": g_data['work_count'],
            "Часов": round(g_data['hours'], 1),
            "Резерв (дн)": ""  # У гостей не считаем резерв в рамках этого маршрута
        }
        for day in all_days: row[day] = g_data['days'].get(day, "")
        guest_rows.append(row)

    # 5. СБОР СЫРЫХ ДАННЫХ ДЛЯ ГЛОБАЛЬНОГО СВОДА (ГОСТИ)
    # Нам нужно передать наружу: кто, в какой день, что сделал, и какой это был маршрут
    # { did: { 'obj': d_obj, 'days': { day: "val №Route" } } }
    guest_raw_global = {}
    for did, g_data in guest_drivers_data.items():
        guest_raw_global[did] = {
            'obj': g_data['obj'],
            'updates': {}  # day -> "val №Route"
        }
        for day, val in g_data['days'].items():
            guest_raw_global[did]['updates'][day] = f"{val} №{route_number}"

    # 6. СТАТИСТИКА
    route_plan = schedule_counts.get(str(route_number), {'workday': 0, 'weekend': 0})
    stat_total_drivers = len(native_drivers_map)

    row_plan = {"Маршрут": "Количество смен по расписанию", "Таб.№": "", "График": "", "Смен": "", "Часов": "",
                "Резерв (дн)": ""}
    row_fact = {"Маршрут": "Количество водителей, вышедших на смену по расписанию", "Таб.№": "", "График": "",
                "Смен": "", "Часов": "", "Резерв (дн)": ""}
    row_reserv = {"Маршрут": "Количество водителей, которым не хватило наряда в рабочий день", "Таб.№": "",
                  "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""}
    row_total = {"Маршрут": "Всего водителей", "Таб.№": stat_total_drivers, "График": "", "Смен": "", "Часов": "",
                 "Резерв (дн)": ""}

    for day in all_days:
        dt = date(SELECTED_YEAR, month_num, day)
        is_weekend = dt.weekday() >= 5
        row_plan[day] = route_plan['weekend'] if is_weekend else route_plan['workday']
        row_fact[day] = stat_active[day]
        row_reserv[day] = stat_reserve_true[day]

    stats_block = [row_plan, row_fact, row_reserv, row_total]

    daily_stats_raw = {
        'plan': {d: row_plan[d] for d in all_days},
        'fact': {d: row_fact[d] for d in all_days},
        'reserve_true': {d: stat_reserve_true[d] for d in all_days},
        'total_drivers': stat_total_drivers
    }

    return active_rows, reserve_rows, guest_rows, stats_block, daily_stats_raw, guest_raw_global


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
    results_dir = os.path.join("data", "results", f"{month_str_num}_{SELECTED_MONTH}_{SELECTED_YEAR}")
    search_pattern = os.path.join(results_dir, f"simulation_*_{SELECTED_MONTH}_{SELECTED_YEAR}.json")
    found_files = glob.glob(search_pattern)

    if not found_files:
        logger.error(f"Файлы симуляции не найдены в {results_dir}")
        return

    with open(found_files[0], 'r') as f:
        tmp = json.load(f)
        all_days = sorted([int(k) for k in tmp.keys() if k.isdigit()])

    target_route = str(SELECTED_ROUTE) if not PROCESS_ALL_ROUTES else None

    os.makedirs(os.path.dirname(SUMMARY_REPORT_FILE), exist_ok=True)
    writer = pd.ExcelWriter(SUMMARY_REPORT_FILE, engine='openpyxl')

    # Глобальные контейнеры
    global_natives = []  # Список строк
    global_reserves_native = []

    # Словарь для ИСТИННЫХ резервных водителей (у которых нет маршрута)
    # { did: { 'obj': d, 'days': {1: '..', 2: '..'} } }
    global_unassigned_guests = {}

    global_stats_sum = {
        'plan': {d: 0 for d in all_days}, 'fact': {d: 0 for d in all_days},
        'reserve_true': {d: 0 for d in all_days}, 'total_drivers_sum': 0
    }

    dow_row = get_day_of_week_row(SELECTED_YEAR, m_num, all_days)

    def get_route_num(path):
        m = re.search(r"simulation_(\d+)_", os.path.basename(path))
        return int(m.group(1)) if m else 9999

    found_files.sort(key=get_route_num)

    processed_count = 0

    for file_path in found_files:
        route_num = str(get_route_num(file_path))
        if target_route and route_num != target_route: continue
        processed_count += 1

        route_assigned_drivers = [d for d in db.drivers if
                                  str(d.assigned_route_number) == route_num and d.month == SELECTED_MONTH]

        active, reserve, guests, stats, raw_stats, guest_global_updates = process_route(
            route_num, file_path, route_assigned_drivers, db.drivers, absences_map, schedule_counts, m_num, all_days
        )

        if PROCESS_ALL_ROUTES:
            global_natives.extend(active)
            global_reserves_native.extend(reserve)
            global_stats_sum['total_drivers_sum'] += raw_stats['total_drivers']
            for d in all_days:
                global_stats_sum['plan'][d] += raw_stats['plan'][d]
                global_stats_sum['fact'][d] += raw_stats['fact'][d]
                global_stats_sum['reserve_true'][d] += raw_stats['reserve_true'][d]

            # Агрегация гостей для глобального свода
            # Добавляем только тех, кто реально "Ничей" (True Reserve)
            for did, info in guest_global_updates.items():
                d_obj = info['obj']
                # Если у водителя нет маршрута или он "0"
                if not d_obj.assigned_route_number or d_obj.assigned_route_number == "0":
                    if did not in global_unassigned_guests:
                        global_unassigned_guests[did] = {'obj': d_obj, 'days': {}}
                    # Мержим дни (добавляем работу с указанием маршрута)
                    for day, val_with_route in info['updates'].items():
                        global_unassigned_guests[did]['days'][day] = val_with_route

        # --- ЗАПИСЬ ЛИСТА МАРШРУТА ---
        sheet_rows = [dow_row]

        h_act = {"Таб.№": "РАБОЧЕЕ ЯДРО", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""}
        for d in all_days: h_act[d] = ""
        sheet_rows.append(h_act)
        for r in active: c = r.copy(); del c["Маршрут"]; sheet_rows.append(c)

        sep = {k: "" for k in h_act}
        sheet_rows.append(sep)

        h_res = {"Таб.№": "ИЗБЫТОЧНЫЙ РЕЗЕРВ", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""}
        for d in all_days: h_res[d] = ""
        sheet_rows.append(h_res)
        for r in reserve: c = r.copy(); del c["Маршрут"]; sheet_rows.append(c)

        sheet_rows.append(sep)

        for sr in stats:
            sr_c = sr.copy();
            title = sr_c["Маршрут"];
            del sr_c["Маршрут"]
            if "Всего водителей" in title:
                val = sr_c["Таб.№"];
                sr_c["Таб.№"] = title;
                sr_c["График"] = val
            else:
                sr_c["Таб.№"] = title
            sheet_rows.append(sr_c)

        # Блок Привлеченных (ниже статистики)
        if guests:
            sheet_rows.append(sep)
            h_guest = {"Таб.№": "ПРИВЛЕЧЕННЫЕ ВОДИТЕЛИ, НЕ ПРИКРЕПЛЕННЫЕ К ДРУГИМ МАРШРУТАМ", "График": "", "Смен": "", "Часов": "",
                       "Резерв (дн)": ""}
            for d in all_days: h_guest[d] = ""
            sheet_rows.append(h_guest)
            for r in guests: c = r.copy(); del c["Маршрут"]; sheet_rows.append(c)

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

        # 1. Свои Активные
        h_glob = {"Маршрут": "РАБОЧЕЕ ЯДРО", "Таб.№": "", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""}
        for d in all_days: h_glob[d] = ""
        common_rows.append(h_glob)
        common_rows.extend(global_natives)
        common_rows.append(sep)

        # 2. Свои Резерв
        h_glob_res = {"Маршрут": "ИЗБЫТОЧНЫЙ РЕЗЕРВ", "Таб.№": "", "График": "", "Смен": "", "Часов": "",
                      "Резерв (дн)": ""}
        for d in all_days: h_glob_res[d] = ""
        common_rows.append(h_glob_res)
        common_rows.extend(global_reserves_native)
        common_rows.append(sep)

        # 3. Статистика
        g_plan = {"Маршрут": "Количество смен по расписанию", "Таб.№": "", "График": "", "Смен": "", "Часов": "",
                  "Резерв (дн)": ""}
        g_fact = {"Маршрут": "Количество водителей, вышедших на смену по расписанию", "Таб.№": "", "График": "",
                  "Смен": "", "Часов": "", "Резерв (дн)": ""}
        g_res = {"Маршрут": "Количество водителей, которым не хватило наряда в рабочий день", "Таб.№": "", "График": "",
                 "Смен": "", "Часов": "", "Резерв (дн)": ""}
        g_tot = {"Маршрут": "Всего водителей", "Таб.№": global_stats_sum['total_drivers_sum'], "График": "", "Смен": "",
                 "Часов": "", "Резерв (дн)": ""}

        for d in all_days:
            g_plan[d] = global_stats_sum['plan'][d]
            g_fact[d] = global_stats_sum['fact'][d]
            g_res[d] = global_stats_sum['reserve_true'][d]

        common_rows.extend([g_plan, g_fact, g_res, g_tot])

        # 4. Резервные (незакрепленные) водители
        if global_unassigned_guests:
            common_rows.append(sep)
            h_unassigned = {"Маршрут": "РЕЗЕРВ (НЕ ЗАКРЕПЛЕННЫЕ)", "Таб.№": "", "График": "", "Смен": "", "Часов": "",
                            "Резерв (дн)": ""}
            for d in all_days: h_unassigned[d] = ""
            common_rows.append(h_unassigned)

            sorted_u = sorted(global_unassigned_guests.keys(), key=lambda x: int(x) if x.isdigit() else x)
            for did in sorted_u:
                info = global_unassigned_guests[did]
                d_obj = info['obj']
                days_data = info['days']
                # Считаем часы (нужно распарсить строку "7.8ч ...")
                # Для простоты пока оставим 0 или посчитаем грубо
                row = {
                    "Маршрут": "Резерв",
                    "Таб.№": did,
                    "График": get_schedule_from_driver(d_obj),
                    "Смен": len(days_data),  # Кол-во дней когда выходил
                    "Часов": "",  # Сложно суммировать строки
                    "Резерв (дн)": ""
                }
                for day in all_days:
                    row[day] = days_data.get(day, "")  # Здесь строка "7.8ч (отд 12) №47"
                common_rows.append(row)

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
    logger.info(f"Сводный отчет готов: {SUMMARY_REPORT_FILE}")


if __name__ == "__main__":
    main()