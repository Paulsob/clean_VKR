import json
import os
import glob
import random
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

ALL_ROUTES = ["9", "20", "21", "47", "48", "55", "61"]


def generate_global_competencies():
    base_dir = os.path.join(project_root, "env_synthetic", "data", "drivers_json")

    search_pattern = os.path.join(base_dir, "**", "*.json")
    all_files = glob.glob(search_pattern, recursive=True)

    if not all_files:
        print("Файлы с водителями не найдены!")
        return

    print(f"Найдено файлов с водителями: {len(all_files)}")

    # ШАГ 1: Собираем все уникальные ID водителей по ключу 'tab_number'
    unique_driver_ids = set()
    for file_path in all_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

            drivers_list = data.get("drivers", []) if isinstance(data, dict) else data

            for d in drivers_list:
                if "tab_number" in d:
                    unique_driver_ids.add(str(d["tab_number"]))

    all_drivers = list(unique_driver_ids)

    if not all_drivers:
        print("Не удалось найти 'tab_number' водителей в файлах")
        return

    random.shuffle(all_drivers)
    total = len(all_drivers)
    print(f"Найдено уникальных водителей: {total}")

    # ШАГ 2: Создаем карту компетенций
    competency_map = {}

    q10 = int(total * 0.10)
    q25 = int(total * 0.25)
    q50 = int(total * 0.50)

    for i, d_id in enumerate(all_drivers):
        if i < q10:
            competency_map[d_id] = {
                "routes": random.sample(ALL_ROUTES, 1),
            }
        elif i < q10 + q25:
            competency_map[d_id] = {"routes": ["ALL"]}
        elif i < q10 + q25 + q50:
            competency_map[d_id] = {
                "routes": random.sample(ALL_ROUTES, 3),
            }
        else:
            competency_map[d_id] = {
                "routes": random.sample(ALL_ROUTES, len(ALL_ROUTES) - 1),
            }

    # ШАГ 3: Записываем допуски обратно
    for file_path in all_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        drivers_list = data.get("drivers", []) if isinstance(data, dict) else data

        for d in drivers_list:
            d_id = str(d.get("tab_number"))
            if d_id in competency_map:
                d["allowed_routes"] = competency_map[d_id]["routes"]

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    print("Допуски успешно сгенерированы и сохранены во все исходные файлы!")


if __name__ == "__main__":
    generate_global_competencies()