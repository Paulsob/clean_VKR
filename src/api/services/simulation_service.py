import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional, List
from src.api.api_models import TaskStatus, SimulationRequest
from src.core.run_simulation import main as run_simulation_main


class SimulationService:
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self.active_task_id: Optional[str] = None

    def get_task(self, task_id: str) -> Optional[Dict]:
        return self.tasks.get(task_id)

    async def _execute_simulation(self, task_id: str, req: SimulationRequest):
        """Внутренний метод для запуска тяжелой логики"""
        try:
            # Выполняем синхронную функцию в отдельном потоке,
            # передавая параметры напрямую (БЕЗ изменения config.py)
            await asyncio.get_event_loop().run_in_executor(
                None,
                run_simulation_main,
                req.month,
                req.year,
                req.routes,
                req.mode.value
            )

            self.tasks[task_id].update({
                "status": TaskStatus.COMPLETED,
                "progress": 1.0,
                "completed_at": datetime.now()
            })
        except Exception as e:
            self.tasks[task_id].update({
                "status": TaskStatus.FAILED,
                "error": str(e),
                "completed_at": datetime.now()
            })
        finally:
            if self.active_task_id == task_id:
                self.active_task_id = None

    def start_task(self, request: SimulationRequest, background_tasks) -> str:
        task_id = str(uuid.uuid4())
        self.active_task_id = task_id

        self.tasks[task_id] = {
            "task_id": task_id,
            "status": TaskStatus.RUNNING,
            "message": "Симуляция запущена",
            "progress": 0.1,
            "started_at": datetime.now(),
            "request": request.dict()
        }

        # Добавляем в BackgroundTasks FastAPI
        background_tasks.add_task(self._execute_simulation, task_id, request)
        return task_id