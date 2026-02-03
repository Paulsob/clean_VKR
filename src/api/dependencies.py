from src.prepare_data.database import DataLoader
from src.api.services.simulation_service import SimulationService

# Инициализируем DataLoader один раз (Singleton)
db_loader = DataLoader()
db_loader.load_all()

# Инициализируем сервис симуляций
sim_service = SimulationService()

def get_db():
    return db_loader

def get_sim_service():
    return sim_service