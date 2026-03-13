import json

input_file = 'drivers_9.json'
output_file = 'drivers_9.json'

try:
    # Читаем файл
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Проходим по всем водителям и удаляем лишние ключи
    if 'drivers' in data:
        for driver in data['drivers']:
            driver.pop('allowed_routes', None)  # Удаляем routes, если есть
            driver.pop('allowed_trams', None)   # Удаляем trams, если есть

    # Записываем результат в новый файл
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Готово! Очищенный файл сохранен как {output_file}")

except Exception as e:
    print(f"Произошла ошибка: {e}")