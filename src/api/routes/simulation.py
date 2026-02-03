from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from src.api.api_models import SimulationRequest, TaskResponse
from src.api.dependencies import get_sim_service

router = APIRouter()


@router.post("/run", response_model=TaskResponse)
async def run_simulation(
        request: SimulationRequest,
        background_tasks: BackgroundTasks,
        service=Depends(get_sim_service)
):
    if service.active_task_id:
        raise HTTPException(status_code=409, detail="Симуляция уже выполняется")

    task_id = service.start_task(request, background_tasks)
    return TaskResponse(task_id=task_id, status="running", message="Задача поставлена в очередь")


@router.get("/status/{task_id}", response_model=TaskResponse)
async def get_status(task_id: str, service=Depends(get_sim_service)):
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task