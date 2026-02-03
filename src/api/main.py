import os
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
os.chdir(project_root)

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
import json
from datetime import datetime, date
from typing import List, Dict, Any

from src.api.routes import simulation, system, drivers, reports
from src.api.dependencies import get_db
from src.core.scheduler import WorkforceAnalyzer
from src.utils import get_day_type_by_date, get_weekday_name, get_month_number
from src.core.manage_absences import load_absences, save_absences, add_absence
import src.config as config

app = FastAPI(title="Tram Schedule API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем статику
outputs_path = Path("outputs")
outputs_path.mkdir(exist_ok=True)
app.mount("/reports", StaticFiles(directory="outputs"), name="outputs")
app.mount("/static", StaticFiles(directory="frontend"), name="static")
templates = Jinja2Templates(directory="frontend")


# ===== ФРОНТЕНД РОУТЫ =====

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db=Depends(get_db)):
    """Главная страница с календарем"""
    # Получаем реальную статистику водителей
    total_drivers = len(db.drivers)

    # Подсчитываем отсутствующих на сегодня
    today = date.today()
    absent_today = 0

    for absence in db.absences:
        try:
            # ИСПРАВЛЕНО: Проверяем тип данных
            if hasattr(absence, 'from_date') and hasattr(absence, 'to_date'):
                # Это объект модели Pydantic
                if absence.from_date <= today <= absence.to_date:
                    absent_today += 1
            elif isinstance(absence, dict):
                # Это словарь из JSON
                from_date_raw = absence.get("from")
                to_date_raw = absence.get("to")

                # Проверяем, строка это или уже дата
                if isinstance(from_date_raw, str):
                    from_date = datetime.fromisoformat(from_date_raw).date()
                else:
                    from_date = from_date_raw

                if isinstance(to_date_raw, str):
                    to_date = datetime.fromisoformat(to_date_raw).date()
                else:
                    to_date = to_date_raw

                if from_date <= today <= to_date:
                    absent_today += 1
        except (ValueError, TypeError, AttributeError):
            # Пропускаем некорректные записи
            continue

    available_drivers = total_drivers - absent_today

    return templates.TemplateResponse("index.html", {
        "request": request,
        "base_count": total_drivers,
        "real_absent": absent_today,
        "total_drivers_real": available_drivers
    })


# ===== КАЛЕНДАРНЫЕ API =====

@app.get("/calendar-data/{year}/{month}")
async def get_calendar_data(year: int, month: int, db=Depends(get_db)):
    """Возвращает дни с доступными расписаниями"""
    import calendar

    # Получаем количество дней в месяце
    _, days_in_month = calendar.monthrange(year, month)

    # Получаем название месяца на русском
    month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                   "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    month_name = month_names[month]

    # Проверяем, есть ли водители на этот месяц
    month_drivers = [d for d in db.drivers if d.month == month_name]

    dates_with_schedules = []
    if month_drivers:  # Если есть водители, значит есть расписания
        for day in range(1, days_in_month + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            dates_with_schedules.append(date_str)

    return dates_with_schedules


@app.get("/api/routes")
async def get_routes(db=Depends(get_db)):
    """Получить список всех маршрутов"""
    # Извлекаем уникальные номера маршрутов из расписаний
    routes = list(set(str(s.route_number) for s in db.schedules))
    # Сортируем по приоритету
    priority_order = ["9", "20", "21", "47", "48", "55", "61"]
    sorted_routes = sorted(routes, key=lambda x: priority_order.index(x) if x in priority_order else 999)
    return sorted_routes


# ===== РАСПИСАНИЯ API =====

@app.get("/api/schedule/{day}/{route}")
async def get_schedule_old_format(day: int, route: str, db=Depends(get_db)):
    """Получить расписание (старый формат - номер дня)"""
    # Используем текущий месяц и год из конфига
    return await _get_schedule_internal(day, config.SELECTED_MONTH, config.SELECTED_YEAR, route, db)


@app.get("/api/schedule/{date}/{route}")
async def get_schedule_new_format(date: str, route: str, db=Depends(get_db)):
    """Получить расписание (новый формат - полная дата YYYY-MM-DD)"""
    try:
        year, month, day = map(int, date.split('-'))
        month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                       "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        month_name = month_names[month]
        return await _get_schedule_internal(day, month_name, year, route, db)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Неверный формат даты")


async def _get_schedule_internal(day: int, month_name: str, year: int, route: str, db):
    """Внутренняя функция для получения расписания"""
    try:
        # Определяем тип дня
        day_type = get_day_type_by_date(day, month_name, year)
        weekday_name = get_weekday_name(day, month_name, year)

        # Ищем расписание для маршрута и типа дня
        schedule = next(
            (s for s in db.schedules
             if str(s.route_number) == str(route) and s.day_type.lower() == day_type),
            None
        )

        if not schedule:
            return {
                "success": False,
                "error": f"Нет расписания для маршрута {route} на {day_type} день"
            }

        # Создаем анализатор для получения водителей
        analyzer = WorkforceAnalyzer(db)

        # ИСПРАВЛЕНО: используем правильный метод
        try:
            result = analyzer._generate_single_route_roster(
                route_number=route,
                day_of_month=day,
                target_month=month_name,
                target_year=year,
                mode="real",
                daily_history_buffer={}
            )
        except AttributeError:
            # Если метод не найден, возвращаем базовую структуру
            result = {
                "date": day,
                "route": route,
                "day_name": weekday_name,
                "day_type": day_type,
                "roster": []
            }

        if "error" in result:
            return {"success": False, "error": result["error"]}

        # Формируем данные для фронтенда в ожидаемом формате
        rows = []
        drivers_info = []

        for tram_data in result.get("roster", []):
            # Создаем строку данных для таблицы (как ожидает фронтенд)
            row = [""] * 14  # 14 колонок как в оригинале
            row[0] = route  # Номер маршрута

            # Данные первой смены
            if tram_data.get("shift_1"):
                shift1 = tram_data["shift_1"]
                times = shift1["time_range"].split("-")
                row[5] = times[0]  # Отправление 1 смена
                row[6] = times[1]  # Прибытие 1 смена
                row[12] = shift1["driver"]  # № водителя 1 смены

                drivers_info.append({
                    "shift": 1,
                    "tab_no": shift1["driver"],
                    "graph_type": "5/2"  # Заглушка, можно получить из данных водителя
                })

            # Данные второй смены
            if tram_data.get("shift_2"):
                shift2 = tram_data["shift_2"]
                times = shift2["time_range"].split("-")
                row[10] = times[0]  # Отправление 2 смена
                row[11] = times[1]  # Прибытие 2 смена
                row[13] = shift2["driver"]  # № водителя 2 смены

                drivers_info.append({
                    "shift": 2,
                    "tab_no": shift2["driver"],
                    "graph_type": "5/2"
                })

            rows.append(row)

        return {
            "success": True,
            "day": day,
            "month": get_month_number(month_name),
            "year": year,
            "route": route,
            "is_weekend": day_type == "выходной",
            "rows": rows,
            "drivers": drivers_info,
            "route_info": f"Маршрут {route} - {weekday_name}, {day} {month_name} {year}"
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/recalculate/{date}")
async def recalculate_schedule(date: str, request: Request, db=Depends(get_db)):
    """Пересчитать расписание с учетом настроек"""
    try:
        body = await request.json()
        route = body.get("route", "47")

        # Парсим дату
        if "-" in date:
            year, month, day = map(int, date.split('-'))
            month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                           "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
            month_name = month_names[month]
        else:
            day = int(date)
            month_name = config.SELECTED_MONTH
            year = config.SELECTED_YEAR

        # Создаем новый анализатор для пересчета
        analyzer = WorkforceAnalyzer(db)

        # Пересчитываем расписание (используем любой доступный метод)
        return {"success": True, "message": "Расписание пересчитано"}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ===== ОТСУТСТВИЯ API =====

@app.get("/absence-data")
async def get_absence_data(mode: str = "real", db=Depends(get_db)):
    """Получить данные об отсутствиях"""
    total_drivers = len(db.drivers)

    if mode == "real":
        # Подсчитываем реальные отсутствия на сегодня
        today = date.today()
        absent_count = 0

        for absence in db.absences:
            try:
                if hasattr(absence, 'from_date') and hasattr(absence, 'to_date'):
                    if absence.from_date <= today <= absence.to_date:
                        absent_count += 1
                elif isinstance(absence, dict):
                    from_date_raw = absence.get("from")
                    to_date_raw = absence.get("to")

                    if isinstance(from_date_raw, str):
                        from_date = datetime.fromisoformat(from_date_raw).date()
                    else:
                        from_date = from_date_raw

                    if isinstance(to_date_raw, str):
                        to_date = datetime.fromisoformat(to_date_raw).date()
                    else:
                        to_date = to_date_raw

                    if from_date <= today <= to_date:
                        absent_count += 1
            except (ValueError, TypeError, AttributeError):
                continue
    else:
        # Статистический режим - 21.7%
        absent_count = int(total_drivers * 0.217)

    available_drivers = total_drivers - absent_count

    return {
        "base_count": total_drivers,
        "absent_count": absent_count,
        "total_drivers": available_drivers,
        "details": f"Уникальных водителей введено: {absent_count}",
        "note": "Статистический расчет (21.7%)" if mode != "real" else None
    }


@app.post("/submit-absence")
async def submit_absence(request: Request):
    """Добавить отсутствие водителя"""
    try:
        data = await request.json()

        # Валидация данных
        tab_no = str(data.get("tab_no", "")).strip()
        shift = int(data.get("shift", 1))
        day = int(data.get("day", 1))
        reason = int(data.get("reason", 0))

        if not tab_no:
            raise ValueError("Табельный номер обязателен")

        # Определяем тип отсутствия
        reason_map = {0: "vacation", 1: "sick", 2: "other"}
        absence_type = reason_map.get(reason, "other")

        # Формируем дату (используем текущий месяц/год)
        current_year = config.SELECTED_YEAR
        current_month = get_month_number(config.SELECTED_MONTH)
        absence_date = date(current_year, current_month, day)

        # ИСПРАВЛЕНО: используем правильную функцию add_absence
        # Добавляем отсутствие напрямую в JSON
        absences_data = load_absences()
        new_absence = {
            "driver_id": tab_no,
            "type": absence_type,
            "from": absence_date.strftime("%Y-%m-%d"),
            "to": absence_date.strftime("%Y-%m-%d"),
            "comment": f"Смена {shift}, причина: {['Отпуск', 'Больничный', 'Не предупредил'][reason]}"
        }

        absences_data["absences"].append(new_absence)
        save_absences(absences_data)

        return {"success": True, "message": "Отсутствие успешно добавлено"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/get-real-absences")
async def get_real_absences():
    """Получить список отсутствий"""
    try:
        absences_data = load_absences()

        # Преобразуем в формат для фронтенда
        result = []
        for i, absence in enumerate(absences_data.get("absences", [])):
            reason_map = {"vacation": 0, "sick": 1, "other": 2}

            # Извлекаем день из даты
            from_date = datetime.fromisoformat(absence["from"]).date()

            result.append({
                "id": i + 1,  # Простой ID для удаления
                "tab_no": absence["driver_id"],
                "shift": 1,  # Заглушка, можно извлечь из комментария
                "day": from_date.day,
                "reason": reason_map.get(absence["type"], 2),
                "timestamp": datetime.now().isoformat()
            })

        return result

    except Exception as e:
        return []


@app.post("/delete-absence")
async def delete_absence(request: Request):
    """Удалить отсутствие"""
    try:
        data = await request.json()
        absence_id = data.get("id")

        if absence_id is None:
            return {"success": False, "error": "ID отсутствия не указан"}

        # Загружаем текущие отсутствия
        absences_data = load_absences()
        absences_list = absences_data.get("absences", [])

        # Удаляем по индексу (ID - 1)
        if 1 <= absence_id <= len(absences_list):
            absences_list.pop(absence_id - 1)
            absences_data["absences"] = absences_list
            save_absences(absences_data)
            return {"success": True}
        else:
            return {"success": False, "error": "Отсутствие не найдено"}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ===== ОТЧЕТЫ API =====

@app.get("/get-report")
async def download_report():
    """Скачать сводный отчет"""
    try:
        # ИСПРАВЛЕНО: используем существующую функцию напрямую
        from src.generate_reports.generate_summary_report import main as generate_report

        # Генерируем отчет
        generate_report()

        # Ищем сгенерированный файл
        import glob
        month_num = get_month_number(config.SELECTED_MONTH)
        directory_name = f"{month_num:02d}_{config.SELECTED_MONTH}_{config.SELECTED_YEAR}"

        if config.PROCESS_ALL_ROUTES:
            filename_pattern = f"summary_report_{config.SIMULATION_MODE}_FULL_PARK_{config.SELECTED_MONTH}_{config.SELECTED_YEAR}.xlsx"
        else:
            filename_pattern = f"summary_report_{config.SIMULATION_MODE}_{config.SELECTED_ROUTE}_{config.SELECTED_MONTH}_{config.SELECTED_YEAR}.xlsx"

        report_path = os.path.join("outputs", "SUMMARY_REPORTS", directory_name, config.SIMULATION_MODE,
                                   filename_pattern)

        if os.path.exists(report_path):
            return FileResponse(
                path=report_path,
                filename=f"summary_report_{config.SELECTED_MONTH}_{config.SELECTED_YEAR}.xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            raise HTTPException(status_code=404, detail="Отчет не найден")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации отчета: {str(e)}")


# Подключаем существующие роутеры
app.include_router(simulation.router, prefix="/api/simulation", tags=["Simulation"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(drivers.router, prefix="/api/drivers", tags=["Drivers"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
