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

# Импорт конфига
from src.config import (
    SELECTED_MONTH, SELECTED_YEAR, SELECTED_ROUTE, PROCESS_ALL_ROUTES,
    SIMULATION_MODE, USE_SYNTHETIC_DATA, SELECTED_PATTERN, SIMULATION_DURATION
)
from src.prepare_data.database import DataLoader
from src.logger import get_logger

logger = get_logger("SummaryReport")


def get_month_sequence(start_month_name, start_year, duration_months):
    months_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    try:
        start_idx = months_names.index(start_month_name)
    except ValueError:
        start_idx = 0

    sequence = []
    current_idx = start_idx
    current_year = start_year

    for _ in range(duration_months):
        m_name = months_names[current_idx]
        sequence.append((m_name, current_year))
        current_idx += 1
        if current_idx >= 12:
            current_idx = 0
            current_year += 1
    return sequence


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
    ws.freeze_panes = 'A3'

    # === ЦВЕТА ===
    fill_work = PatternFill("solid", fgColor="C6EFCE")
    fill_work_weekend = PatternFill("solid", fgColor="FFC000")

    fill_reserve = PatternFill("solid", fgColor="FFC7CE")
    fill_alarm = PatternFill("solid", fgColor="FF0000")
    fill_warn = PatternFill("solid", fgColor="FF9900")  # Оранжевый (!)
    fill_norm = PatternFill("solid", fgColor="5B9BD5")

    fill_rest = PatternFill("solid", fgColor="F2F2F2")
    fill_sick = PatternFill("solid", fgColor="FFFF00")

    fill_header = PatternFill("solid", fgColor="4472C4")
    fill_stat = PatternFill("solid", fgColor="D9E1F2")
    fill_guest_header = PatternFill("solid", fgColor="70AD47")
    fill_any_header = PatternFill("solid", fgColor="FFD966")

    font_header = Font(bold=True, color="FFFFFF")
    font_bold = Font(bold=True)
    font_white_bold = Font(bold=True, color="FFFFFF")

    border = Border(left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin'))

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        first_val = str(row[0].value) if row[0].value else ""

        is_header_group = first_val in ["РАБОЧЕЕ ЯДРО"]
        is_guest_header = "ПРИВЛЕЧЕННЫЕ" in first_val or "РЕЗЕРВ (НЕ ЗАКРЕПЛЕННЫЕ)" in first_val
        is_any_header = "РЕЗЕРВ ANY" in first_val

        is_stat_block = any(k in first_val for k in ["Количество закрытых", "Количество незакрытых", "Всего водителей"])
        is_dow_row = str(row[-1].value) in ["Пн", "Вт", "Сб", "Вс"] or "День недели" in str(row[5].value)

        if is_header_group:
            for cell in row: cell.fill = fill_header; cell.font = font_header
            continue
        if is_guest_header:
            for cell in row: cell.fill = fill_guest_header; cell.font = font_header
            continue
        if is_any_header:
            for cell in row: cell.fill = fill_any_header; cell.font = font_bold
            continue
        if is_stat_block:
            for cell in row: cell.fill = fill_stat; cell.font = font_bold; cell.border = border
            continue

        for cell in row:
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=False)
            val = str(cell.value) if cell.value else ""

            if is_dow_row:
                cell.font = font_bold
                if val in ["Сб", "Вс"]: cell.fill = PatternFill("solid", fgColor="E2EFDA")
                continue

            # === ЛОГИКА ОКРАШИВАНИЯ ЯЧЕЕК ===
            if "МАЛО ОТДЫХА" in val:  # Это критический красный
                cell.fill = fill_alarm
                cell.font = font_white_bold

            elif "(!)" in val:  # Это мягкое предупреждение (Оранжевый)
                cell.fill = fill_warn

            elif "ЛИМИТ" in val:
                cell.fill = fill_norm
                cell.font = font_white_bold

            elif "РЕЗЕРВ" in val:
                cell.fill = fill_reserve

            elif "[ВЫХ]" in val:
                cell.fill = fill_work_weekend
                cell.value = val.replace(" [ВЫХ]", "")

            elif "БОЛЬНИЧНЫЙ" in val or "ОТПУСК" in val:
                cell.fill = fill_sick

            elif "ч (" in val:
                cell.fill = fill_work

            elif val in ["В", "B", "О", "Б"]:
                cell.fill = fill_rest

    for column_cells in ws.columns:
        length = 0
        for cell in column_cells:
            if cell.value: length = max(length, len(str(cell.value)))
        adjusted_width = (length + 2) * 1.05
        if adjusted_width > 55: adjusted_width = 55
        ws.column_dimensions[get_column_letter(column_cells[0].column)].width = adjusted_width


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


def create_stat_rows(stats_dict, total_drivers_count, all_days):
    rows = []

    def make_row(title, data_key):
        r = {"Маршрут": title, "Таб.№": "", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""}
        for d in all_days:
            if data_key in stats_dict[d]:
                r[d] = stats_dict[d][data_key]
            elif data_key == 'unclosed':
                plan = stats_dict[d].get('plan_shifts', 0)
                closed = stats_dict[d].get('closed_shifts', 0)
                r[d] = max(0, plan - closed)
            else:
                r[d] = 0
        return r

    rows.extend([
        make_row("Количество закрытых смен", 'closed_shifts'),
        make_row("Количество незакрытых смен", 'unclosed'),
        make_row("Количество смен по расписанию", 'plan_shifts'),
        make_row("Количество водителей (свой маршрут)", 'drivers_native'),
        make_row("Количество водителей (гости)", 'drivers_guest'),
        make_row("Количество водителей (в выходной)", 'drivers_weekend_work'),
        make_row("Количество водителей на выходном", 'drivers_on_rest'),
        make_row("Количество водителей в резерве/лимите", 'reserve_true'),
        {"Маршрут": "Всего водителей (закрепленных)", "Таб.№": total_drivers_count, "График": "", "Смен": "",
         "Часов": "", "Резерв (дн)": ""}
    ])
    return rows


def process_route(route_number, sim_file_path, assigned_drivers, all_drivers_db, absences_map, schedule_counts,
                  month_num, all_days, year_num, month_name):
    try:
        with open(sim_file_path, "r", encoding="utf-8") as f:
            sim_data = json.load(f)
    except Exception:
        return [], [], [], [], {}, {}, {}

    stats_file_path = sim_file_path.replace("simulation_", "statistics_").replace(".json", ".json")
    actual_drivers_count = None
    try:
        with open(stats_file_path, "r", encoding="utf-8") as f:
            stats_json = json.load(f)
            actual_drivers_count = stats_json.get("TOTAL_DRIVERS_INCLUDING_ABSENT") or stats_json.get(
                "TOTAL_DRIVERS_USED")
    except Exception:
        pass

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

    for day_str, day_res in sim_data.items():
        if not day_str.isdigit(): continue
        day = int(day_str)
        dt = date(year_num, month_num, day)
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
                    val = f"{wh:.1f}ч (отд {rest:.0f})"

                    # Если планировщик добавил (!) в предупреждения, добавляем в текст
                    if s_info.get("warnings"):
                        # Объединяем предупреждения
                        warn_str = " ".join(s_info["warnings"])
                        if "(!)" in warn_str: val += " (!)"

                    current_driver_obj = native_drivers_map.get(raw_did)
                    if not current_driver_obj:
                        current_driver_obj = next(
                            (d for d in all_drivers_db if str(d.id) == raw_did and d.month == month_name), None)

                    if current_driver_obj:
                        status_in_plan = current_driver_obj.get_status_for_day(day)
                        if status_in_plan in ['В', 'B', 'О', 'Б'] or status_in_plan not in ['1', '2']:
                            daily_counters[day]['drivers_weekend_work'] += 1
                            val += " [ВЫХ]"

                    if raw_did in report_data_native:
                        report_data_native[raw_did]['days'][day] = val
                        report_data_native[raw_did]['work_count'] += 1
                        report_data_native[raw_did]['hours'] += wh
                        daily_counters[day]['drivers_native'] += 1
                    else:
                        if raw_did not in guest_drivers_data:
                            if current_driver_obj:
                                guest_drivers_data[raw_did] = {'obj': current_driver_obj, 'days': {}, 'work_count': 0,
                                                               'hours': 0}
                            else:
                                found_guest = next((d for d in all_drivers_db if str(d.id) == raw_did), None)
                                if found_guest:
                                    guest_drivers_data[raw_did] = {'obj': found_guest, 'days': {}, 'work_count': 0,
                                                                   'hours': 0}

                        if raw_did in guest_drivers_data:
                            guest_drivers_data[raw_did]['days'][day] = val
                            guest_drivers_data[raw_did]['work_count'] += 1
                            guest_drivers_data[raw_did]['hours'] += wh
                        daily_counters[day]['drivers_guest'] += 1

    for did, d_obj in native_drivers_map.items():
        driver_absences = absences_map.get(did, {})
        for day in all_days:
            if day in report_data_native[did]['days']: continue

            check_date = date(year_num, month_num, day)
            if check_date in driver_absences:
                a_type = driver_absences[check_date]
                status = "БОЛЬНИЧНЫЙ" if a_type == "sick" else "ОТПУСК"
                report_data_native[did]['days'][day] = status
                continue

            plan = d_obj.get_status_for_day(day)

            if plan in ["1", "2"]:
                day_str = str(day)
                day_info = sim_data.get(day_str, {})
                stat_flags = day_info.get("driver_stat_flags", {})

                if did in stat_flags:
                    reason = stat_flags[did]
                    if reason == "low_rest":
                        report_data_native[did]['days'][day] = "МАЛО ОТДЫХА"
                    elif reason == "norm_limit":
                        report_data_native[did]['days'][day] = "ЛИМИТ"
                    else:
                        report_data_native[did]['days'][day] = "РЕЗЕРВ"
                else:
                    report_data_native[did]['days'][day] = "РЕЗЕРВ"

                report_data_native[did]['reserve_count'] += 1
                daily_counters[day]['reserve_true'] += 1
            else:
                report_data_native[did]['days'][day] = plan
                if plan in ["В", "B", "О", "Б"]:
                    daily_counters[day]['drivers_on_rest'] += 1

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

    guest_raw_global = {}
    any_drivers_raw_global = {}
    for did, g_data in guest_drivers_data.items():
        d_obj = g_data['obj']
        info = {'obj': g_data['obj'], 'updates': {}}
        for day, val in g_data['days'].items(): info['updates'][day] = f"{val} №{route_number}"
        if str(d_obj.assigned_route_number).upper() == "ANY":
            any_drivers_raw_global[did] = info
        else:
            guest_raw_global[did] = info

    stats_block = create_stat_rows(daily_counters, len(native_drivers_map), all_days)
    daily_stats_detailed = daily_counters
    daily_stats_detailed['total_drivers_native'] = actual_drivers_count if actual_drivers_count is not None else len(
        native_drivers_map)

    return active_rows, reserve_rows, guest_rows, stats_block, daily_stats_detailed, guest_raw_global, any_drivers_raw_global


def main():
    logger.info(f"Инициализация генератора отчетов... Режим: {'SYNTHETIC' if USE_SYNTHETIC_DATA else 'REAL'}")
    db = DataLoader()
    db.load_all()
    absences_map = prepare_absences_map(db.absences)
    schedule_counts = prepare_schedule_counts(db.schedules)
    month_map = {"Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6,
                 "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12}
    timeline = get_month_sequence(SELECTED_MONTH, SELECTED_YEAR, SIMULATION_DURATION)
    logger.info(f"Будут сформированы отчеты для: {timeline}")

    for current_month, current_year in timeline:
        logger.info(f"--> Отчет за {current_month} {current_year}")
        m_num = month_map.get(current_month, 1)
        month_str_num = f"{m_num:02d}"

        if USE_SYNTHETIC_DATA:
            base_results_dir = os.path.join("env_synthetic", "data", "results", f"{SELECTED_PATTERN}",
                                            f"{month_str_num}_{current_month}_{current_year}", SIMULATION_MODE)
        else:
            base_results_dir = os.path.join("data", "results", f"{month_str_num}_{current_month}_{current_year}",
                                            SIMULATION_MODE)

        search_pattern = os.path.join(base_results_dir,
                                      f"simulation_{SIMULATION_MODE}_*_{current_month}_{current_year}.json")
        found_files = glob.glob(search_pattern)

        if not found_files:
            logger.warning(f"Файлы не найдены: {base_results_dir}. Пропуск.")
            continue

        with open(found_files[0], 'r') as f:
            tmp = json.load(f)
            all_days = sorted([int(k) for k in tmp.keys() if k.isdigit()])

        target_route = str(SELECTED_ROUTE) if not PROCESS_ALL_ROUTES else None
        pattern_suffix = f"_{SELECTED_PATTERN}" if USE_SYNTHETIC_DATA else ""
        filename_summary = f"summary_report_{SIMULATION_MODE}{pattern_suffix}_{'FULL_PARK' if PROCESS_ALL_ROUTES else SELECTED_ROUTE}_{current_month}_{current_year}.xlsx"

        directory_name = f"{month_str_num}_{current_month}_{current_year}"
        output_dir = os.path.join("env_synthetic" if USE_SYNTHETIC_DATA else "", "outputs", "SUMMARY_REPORTS",
                                  directory_name, SIMULATION_MODE)
        dynamic_summary_file = os.path.join(output_dir, filename_summary)
        os.makedirs(os.path.dirname(dynamic_summary_file), exist_ok=True)

        writer = pd.ExcelWriter(dynamic_summary_file, engine='openpyxl')

        global_natives = []
        global_reserves_native = []
        global_unassigned_guests = {}
        global_any_drivers = {}
        global_stats_detailed = {d: {'closed_shifts': 0, 'plan_shifts': 0, 'drivers_native': 0, 'drivers_guest': 0,
                                     'drivers_weekend_work': 0, 'drivers_on_rest': 0, 'reserve_true': 0} for d in
                                 all_days}
        global_total_drivers_count = 0

        overall_stats_file = os.path.join(base_results_dir,
                                          f"statistics_OVERALL_{SIMULATION_MODE}_{current_month}_{current_year}.json")
        overall_drivers_count = None
        try:
            with open(overall_stats_file, "r", encoding="utf-8") as f:
                ostats = json.load(f)
                overall_drivers_count = ostats.get("TOTAL_UNIQUE_DRIVERS_INCLUDING_ABSENT") or ostats.get(
                    "TOTAL_UNIQUE_DRIVERS_ALL_ROUTES")
        except:
            pass

        dow_row = get_day_of_week_row(current_year, m_num, all_days)

        def get_route_num(path):
            m = re.search(f"simulation_{SIMULATION_MODE}_(\\d+)_", os.path.basename(path))
            return int(m.group(1)) if m else 9999

        found_files.sort(key=get_route_num)

        processed_count = 0
        for file_path in found_files:
            route_num = str(get_route_num(file_path))
            if target_route and route_num != target_route: continue
            processed_count += 1

            if USE_SYNTHETIC_DATA:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        c = json.load(f)
                    w_ids = set()
                    for v in c.values():
                        if isinstance(v, dict) and "roster" in v:
                            for t in v["roster"]:
                                for s in ["shift_1", "shift_2"]:
                                    if t.get(s) and t[s].get("driver"):
                                        w_ids.add(t[s]["driver"].split(" ")[0])
                    # Теперь получаем всех подходящих водителей, не только с закрепленным маршрутом
                    route_assigned_drivers = [d for d in db.drivers if str(d.id) in w_ids and d.month == current_month]
                except:
                    route_assigned_drivers = []
            else:
                # Учитываем также водителей с универсальным доступом (ANY)
                route_assigned_drivers = [d for d in db.drivers if
                                          str(d.assigned_route_number) == route_num or
                                          str(d.assigned_route_number).upper() == "ANY" and d.month == current_month]

            active, reserve, guests, stats, detailed, g_glob, any_glob = process_route(
                route_num, file_path, route_assigned_drivers, db.drivers, absences_map, schedule_counts, m_num,
                all_days, current_year, current_month
            )

            if PROCESS_ALL_ROUTES:
                global_natives.extend(active)
                global_reserves_native.extend(reserve)
                global_total_drivers_count += detailed['total_drivers_native']
                for d in all_days:
                    for k in global_stats_detailed[d]: global_stats_detailed[d][k] += detailed[d].get(k, 0)
                for did, info in g_glob.items():
                    if not info['obj'].assigned_route_number or info['obj'].assigned_route_number == "0":
                        if did not in global_unassigned_guests: global_unassigned_guests[did] = {'obj': info['obj'],
                                                                                                 'days': {}}
                        global_unassigned_guests[did]['days'].update(info['updates'])
                for did, info in any_glob.items():
                    if did not in global_any_drivers: global_any_drivers[did] = {'obj': info['obj'], 'days': {}}
                    global_any_drivers[did]['days'].update(info['updates'])

            rows = [dow_row]
            h1 = {"Таб.№": "РАБОЧЕЕ ЯДРО", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""};
            h1.update({d: "" for d in all_days})
            rows.append(h1)
            for r in active: c = r.copy(); del c["Маршрут"]; rows.append(c)

            sep = {k: "" for k in h1}
            if active and reserve: rows.append(sep)
            for r in reserve: c = r.copy(); del c["Маршрут"]; rows.append(c)

            if guests:
                rows.append(sep)
                h2 = {"Таб.№": "ПРИВЛЕЧЕННЫЕ", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""};
                h2.update({d: "" for d in all_days})
                rows.append(h2)
                for r in guests: c = r.copy(); del c["Маршрут"]; rows.append(c)

            rows.append(sep)
            for s in stats: c = s.copy(); t = c["Маршрут"]; del c["Маршрут"]; c["Таб.№"] = t; rows.append(c)

            df = pd.DataFrame(rows)[["Таб.№", "График", "Смен", "Часов", "Резерв (дн)"] + all_days]
            sn = f"Маршрут {route_num}"
            df.to_excel(writer, index=False, sheet_name=sn)
            style_worksheet(writer.sheets[sn], len(all_days))

        if PROCESS_ALL_ROUTES and processed_count > 0:
            logger.info("Формирование общего свода...")
            c_rows = [dow_row]
            h_glob = {"Маршрут": "РАБОЧЕЕ ЯДРО", "Таб.№": "", "График": "", "Смен": "", "Часов": "", "Резерв (дн)": ""};
            h_glob.update({d: "" for d in all_days})
            c_rows.append(h_glob)
            c_rows.extend(global_natives)

            sep = {k: "" for k in h_glob}
            if global_natives and global_reserves_native: c_rows.append(sep)
            c_rows.extend(global_reserves_native)
            c_rows.append(sep)

            if global_unassigned_guests:
                h_un = {"Маршрут": "РЕЗЕРВ (НЕ ЗАКРЕПЛЕННЫЕ)", "Таб.№": "", "График": "", "Смен": "", "Часов": "",
                        "Резерв (дн)": ""};
                h_un.update({d: "" for d in all_days})
                c_rows.append(h_un)
                for did in sorted(global_unassigned_guests.keys(), key=lambda x: int(x) if x.isdigit() else x):
                    info = global_unassigned_guests[did]
                    r = {"Маршрут": "Резерв", "Таб.№": did, "График": get_schedule_from_driver(info['obj']),
                         "Смен": len(info['days']), "Часов": "", "Резерв (дн)": ""}
                    r.update({d: info['days'].get(d, "") for d in all_days})
                    c_rows.append(r)
                c_rows.append(sep)

            final_cnt = overall_drivers_count if overall_drivers_count is not None else global_total_drivers_count
            c_rows.extend(create_stat_rows(global_stats_detailed, final_cnt, all_days))

            df_glob = pd.DataFrame(c_rows)[["Маршрут", "Таб.№", "График", "Смен", "Часов", "Резерв (дн)"] + all_days]
            df_glob.to_excel(writer, index=False, sheet_name="ОБЩИЙ СВОД")
            style_worksheet(writer.sheets["ОБЩИЙ СВОД"], len(all_days))

            wb = writer.book
            if "ОБЩИЙ СВОД" in wb.sheetnames:
                wb._sheets.insert(0, wb._sheets.pop(wb.sheetnames.index("ОБЩИЙ СВОД")))
                wb.active = 0

        writer.close()
        logger.info(f"Готово: {dynamic_summary_file}")


if __name__ == "__main__":
    main()
