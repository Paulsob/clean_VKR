from fastapi import APIRouter, Depends
from src.api.api_models import SystemStatus
from src.api.dependencies import get_db
import src.config as config

router = APIRouter()

@router.get("/status", response_model=SystemStatus)
async def get_system_status(db = Depends(get_db)):
    return SystemStatus(
        status="running",
        current_month=config.SELECTED_MONTH,
        current_year=config.SELECTED_YEAR,
        process_all_routes=config.PROCESS_ALL_ROUTES,
        database_status="connected",
        drivers_count=len(db.drivers),
        routes_count=len(set(str(s.route_number) for s in db.schedules))
    )