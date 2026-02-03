const API_BASE_URL_ABS = "http://localhost:8000";

$(document).ready(function() {
    $('#absenceForm').submit(function(e) {
        e.preventDefault();
        alert("Функция добавления отсутствий временно недоступна (нет API endpoint).");
    });

    loadDriversList();
});

function loadDriversList() {
    $.get(`${API_BASE_URL_ABS}/api/drivers/`, function(data) {
        const container = $('#recentAbsences');

        if (!Array.isArray(data) || data.length === 0) {
            container.html('<li class="list-group-item text-muted">Нет данных</li>');
            return;
        }

        const list = data.slice(0, 5);
        let html = '';

        list.forEach(item => {
            html += `
                <li class="list-group-item">
                    <strong>ID: ${item.id}</strong> <br>
                    <small class="text-muted">Маршрут: ${item.route || '-'} | График: ${item.graph || '-'}</small>
                </li>
            `;
        });

        container.html(html);
        $('.card-header.bg-warning h5').text("Список водителей (API)");
    }).fail(function() {
        $('#recentAbsences').html('<li class="list-group-item text-danger">Ошибка API</li>');
    });
}