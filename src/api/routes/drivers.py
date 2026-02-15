from fastapi import APIRouter, Depends
from src.api.dependencies import get_db
from src.api.api_models import DriverInfo, DriversResponse

router = APIRouter()


@router.get("/", response_model=DriversResponse)
async def get_all_drivers(db=Depends(get_db)):
    """Возвращает список всех водителей из базы"""
    # Предполагаем, что db.drivers - это список объектов водителей
    driver_list = [DriverInfo.from_driver(d) for d in db.drivers]

    return DriversResponse(
        drivers=driver_list,
        total=len(driver_list)
    )