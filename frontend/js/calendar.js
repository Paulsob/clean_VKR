const API_BASE_URL = "http://localhost:8000";

// Глобальные переменные
let currentYear, currentMonth;
let selectedRoute = null; // Будет установлено автоматически
let currentReportData = null; // Сюда скачаем JSON отчета

function initCalendar() {
  const now = new Date();
  currentYear = now.getFullYear();
  currentMonth = now.getMonth(); // 0 = Январь

  const routeSelect = document.getElementById("routeSelect");

  // 1. Получаем список водителей, чтобы собрать доступные маршруты
  fetch(`${API_BASE_URL}/api/drivers/`)
    .then(res => res.json())
    .then(drivers => {
        // drivers - это массив объектов. Нам нужно найти уникальные route
        // Предполагаем, что у водителя есть поле 'route' или он привязан к маршруту
        // Если в API водителей нет поля route, напиши мне.
        // Пока попробуем собрать уникальные значения, если они там есть.

        // ВРЕМЕННОЕ РЕШЕНИЕ: Так как в doc нет эндпоинта списка маршрутов,
        // а endpoint drivers может возвращать просто список людей,
        // давай пока добавим маршруты вручную или из отчетов.
        // Но лучше всего - проанализировать отчеты.

        loadRoutesFromReports(routeSelect);
    })
    .catch(err => {
        console.error("Ошибка загрузки драйверов:", err);
        routeSelect.innerHTML = "<option>Ошибка API</option>";
    });
}

// Функция собирает маршруты из доступных отчетов
function loadRoutesFromReports(routeSelect) {
    fetch(`${API_BASE_URL}/api/reports/`)
    .then(res => res.json())
    .then(reports => {
        // reports - массив файлов. Пример имени: "simulation_real_47_Январь_2026.json"
        // Нам нужно распарсить имена файлов, чтобы понять какие есть маршруты

        const routesSet = new Set();

        reports.forEach(rep => {
            // Пытаемся вытащить номер маршрута из имени файла (например, число между подчеркиваниями)
            // Это ненадежно, но пока единственный способ без отдельного API
            const match = rep.filename.match(/_(\d+)_/);
            if (match && match[1]) {
                routesSet.add(match[1]);
            }
        });

        routeSelect.innerHTML = "";
        const sortedRoutes = Array.from(routesSet).sort((a,b) => a - b);

        if (sortedRoutes.length === 0) {
             const opt = document.createElement("option");
             opt.text = "Нет отчетов / маршрутов";
             routeSelect.add(opt);
        } else {
            sortedRoutes.forEach(r => {
                const opt = document.createElement("option");
                opt.value = r;
                opt.text = `Маршрут ${r}`;
                routeSelect.add(opt);
            });

            // Выбираем первый и грузим календарь
            selectedRoute = sortedRoutes[0];
            routeSelect.value = selectedRoute;

            // Вешаем обработчик
            routeSelect.addEventListener("change", () => {
                selectedRoute = routeSelect.value;
                loadReportForMonth(currentYear, currentMonth);
            });

            // Грузим данные
            loadReportForMonth(currentYear, currentMonth);
        }
    });
}

// Ищем и скачиваем отчет для выбранного Года, Месяца и Маршрута
function loadReportForMonth(year, month) {
    const monthNames = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"];
    const monthName = monthNames[month];

    document.getElementById("calendar-container").innerHTML = "<p class='p-3'>Поиск отчета...</p>";
    currentReportData = null; // Сброс

    fetch(`${API_BASE_URL}/api/reports/`)
    .then(res => res.json())
    .then(reports => {
        // Ищем файл, который содержит Год, Месяц и Маршрут
        // Пример: simulation_real_47_Январь_2026.json
        const foundReport = reports.find(r =>
            r.filename.includes(monthName) &&
            r.filename.includes(year.toString()) &&
            r.filename.includes(`_${selectedRoute}_`) &&
            r.filename.endsWith('.json')
        );

        if (foundReport) {
            // Если отчет нашли - скачиваем его содержимое
            // URL для скачивания: /reports/{folder}/{mode}/{filename}
            // API возвращает нам поле download_url ? Если нет, формируем сами.
            // Предположим, API возвращает полный путь или мы его соберем.

            // Если в объекте report есть ready url:
            let downloadUrl = foundReport.url || `${API_BASE_URL}/reports/${foundReport.folder}/${foundReport.mode}/${foundReport.filename}`;
            // Если url относительный, добавим base
            if(downloadUrl.startsWith('/')) downloadUrl = API_BASE_URL + downloadUrl;

            return fetch(downloadUrl).then(r => r.json());
        } else {
            return null;
        }
    })
    .then(jsonData => {
        currentReportData = jsonData; // Сохраняем в память
        renderCalendar(year, month, !!jsonData);
    })
    .catch(err => {
        console.error("Ошибка отчета:", err);
        renderCalendar(year, month, false);
    });
}

function renderCalendar(year, month, hasData) {
  currentYear = year;
  currentMonth = month;
  const container = document.getElementById("calendar-container");
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const daysInMonth = lastDay.getDate();

  let html = `
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4>${getMonthName(month)} ${year}</h4>
            <div>
                <button class="btn btn-sm btn-outline-secondary" id="prevMonth">&lt;</button>
                <button class="btn btn-sm btn-outline-secondary" id="nextMonth">&gt;</button>
            </div>
        </div>
        <div class="alert ${hasData ? 'alert-success' : 'alert-warning'} py-1">
            ${hasData ? 'Отчет загружен. Нажмите на день для просмотра.' : 'Отчет за этот месяц не найден.'}
        </div>
        <div class="table-responsive">
            <table class="table table-bordered text-center">
                <thead class="table-light"><tr><th>Пн</th><th>Вт</th><th>Ср</th><th>Чт</th><th>Пт</th><th>Сб</th><th>Вс</th></tr></thead>
                <tbody>`;

  let startDayOfWeek = firstDay.getDay() || 7;
  let htmlDays = "";
  for (let i = 1; i < startDayOfWeek; i++) htmlDays += "<td></td>";

  for (let day = 1; day <= daysInMonth; day++) {
    if (startDayOfWeek === 1) htmlDays += "<tr>";

    // Если отчет есть, считаем что данные есть на каждый день месяца
    const canShow = hasData;

    htmlDays += `
            <td class="${canShow ? "table-success" : ""}" style="cursor: pointer;" onclick="showDaySchedule(${day})">
                <div class="day-number">${day}</div>
            </td>`;

    if (startDayOfWeek === 7) { htmlDays += "</tr>"; startDayOfWeek = 0; }
    startDayOfWeek++;
  }

  if (startDayOfWeek !== 1) htmlDays += "</tr>"; // закрыть ряд

  container.innerHTML = html + htmlDays + `</tbody></table></div>`;

  document.getElementById("prevMonth").addEventListener("click", () => changeMonth(-1));
  document.getElementById("nextMonth").addEventListener("click", () => changeMonth(1));
}

function showDaySchedule(day) {
    const display = document.getElementById("scheduleDisplay");

    if (!currentReportData) {
        display.innerHTML = "<div class='alert alert-warning'>Нет данных отчета для отображения.</div>";
        return;
    }

    display.innerHTML = `<h5>Расписание на ${day} число</h5>`;

    // ТУТ ВАЖНО: Нужно знать структуру твоего JSON отчета.
    // Я предполагаю структуру: { "1": [...строки...], "2": [...], ... "31": [...] }
    // ИЛИ массив объектов, где есть поле date/day.

    // Попробуем найти данные по ключу дня (строка или число)
    let dayData = currentReportData[day] || currentReportData[String(day)];

    // Если структура другая (например, массив объектов schedule), придется искать find()
    if (!dayData && Array.isArray(currentReportData)) {
        dayData = currentReportData.filter(row => row.day == day || row.date?.endsWith(`-${day}`));
    }

    if (!dayData || (Array.isArray(dayData) && dayData.length === 0)) {
        display.innerHTML += "<p>Смен на этот день не найдено в отчете.</p>";
        return;
    }

    // Рендер таблицы
    let table = `<table class="table table-striped table-sm"><thead><tr>
        <th>Смена</th><th>Таб. №</th><th>Водитель</th><th>Время</th>
    </tr></thead><tbody>`;

    // Адаптация под структуру данных отчета
    // Если dayData - это массив смен
    if (Array.isArray(dayData)) {
        dayData.forEach(row => {
            // Подставь сюда правильные поля из твоего JSON
            table += `<tr>
                <td>${row.shift_type || row.shift || '-'}</td>
                <td>${row.driver_id || row.tab_no || '-'}</td>
                <td>${row.driver_name || '-'}</td>
                <td>${row.time || '-'}</td>
            </tr>`;
        });
    }

    table += `</tbody></table>`;
    display.innerHTML += table;
}

function changeMonth(delta) {
  let newMonth = currentMonth + delta;
  let newYear = currentYear;
  if (newMonth < 0) { newMonth = 11; newYear--; }
  else if (newMonth > 11) { newMonth = 0; newYear++; }
  loadReportForMonth(newYear, newMonth);
}

function getMonthName(idx) {
  const months = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"];
  return months[idx];
}

document.getElementById('runSimulationBtn').addEventListener('click', function() {
    const statusDiv = document.getElementById('simStatus');
    statusDiv.textContent = "Запуск симуляции...";

    // Берем текущий месяц/год из календаря
    const monthNames = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"];

    const payload = {
        month: monthNames[currentMonth],
        year: currentYear,
        mode: "real"
    };

    fetch('http://localhost:8000/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        statusDiv.textContent = `Задача запущена! ID: ${data.task_id || 'OK'}`;
        // Тут можно запустить опрос статуса (polling), но пока просто выведем сообщение
    })
    .catch(err => {
        statusDiv.textContent = "Ошибка запуска: " + err;
    });
});