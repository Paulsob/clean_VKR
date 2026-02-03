import os
from fastapi import APIRouter
from src.config import RESULTS_DIR
from src.utils import get_month_number  # Используем твою утилиту

router = APIRouter()


@router.get("/")
async def list_reports():
    """Сканирует вложенную структуру и выдает список отчетов с метаданными"""
    all_reports = []
    if not os.path.exists(RESULTS_DIR):
        return {"reports": []}

    # Идем по папкам: RESULTS_DIR / 01_Январь_2026 / real / ...
    for folder in os.listdir(RESULTS_DIR):
        folder_path = os.path.join(RESULTS_DIR, folder)
        if not os.path.isdir(folder_path):
            continue

        # folder это "01_Январь_2026"
        for mode in ["real", "strict"]:
            mode_path = os.path.join(folder_path, mode)
            if os.path.exists(mode_path):
                for file in os.listdir(mode_path):
                    if file.endswith(".json"):
                        file_path = os.path.join(mode_path, file)
                        all_reports.append({
                            "filename": file,
                            "folder": folder,  # 01_Январь_2026
                            "mode": mode,
                            "size_kb": round(os.path.getsize(file_path) / 1024, 1),
                            "url": f"/static/{folder}/{mode}/{file}"  # Для скачивания
                        })

    return {"reports": all_reports}