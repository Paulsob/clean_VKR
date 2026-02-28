# src/path_manager.py
"""
Централизованное управление путями к файлам и директориям проекта.
Устраняет дублирование логики формирования путей.
"""
import os
from typing import Optional
from src.constants import get_month_number


class PathManager:
    """Менеджер путей для проекта симуляции."""
    
    def __init__(self, 
                 base_dir: str,
                 use_synthetic: bool,
                 selected_pattern: Optional[str] = None):
        """
        Args:
            base_dir: Корневая директория проекта
            use_synthetic: Использовать синтетические данные
            selected_pattern: Паттерн графика (например, "5x2")
        """
        self.base_dir = base_dir
        self.use_synthetic = use_synthetic
        self.selected_pattern = selected_pattern
        
        # Определяем окружение
        self.env_folder = "env_synthetic" if use_synthetic else "env_real"
        self.env_dir = os.path.join(base_dir, self.env_folder)
        
        # Базовые директории
        self.data_dir = os.path.join(self.env_dir, "data")
        self.outputs_dir = os.path.join(self.env_dir, "outputs")
        
        # Результаты и история с учетом паттерна
        if use_synthetic and selected_pattern:
            self.results_dir = os.path.join(self.data_dir, "results", selected_pattern)
            self.history_dir = os.path.join(self.env_dir, "history", selected_pattern)
        else:
            self.results_dir = os.path.join(self.data_dir, "results")
            self.history_dir = os.path.join(self.env_dir, "history")
    
    def get_month_folder_name(self, month_name: str, year: int) -> str:
        """
        Формирует имя папки для месяца: "01_Январь_2026"
        
        Args:
            month_name: Название месяца
            year: Год
            
        Returns:
            Имя папки
        """
        month_num = get_month_number(month_name)
        return f"{month_num:02d}_{month_name}_{year}"
    
    def get_simulation_file_path(self, 
                                  route: str, 
                                  month: str, 
                                  year: int, 
                                  mode: str) -> str:
        """
        Путь к файлу результатов симуляции.
        
        Args:
            route: Номер маршрута
            month: Название месяца
            year: Год
            mode: Режим симуляции (strict/real)
            
        Returns:
            Полный путь к файлу
        """
        folder_name = self.get_month_folder_name(month, year)
        filename = f"simulation_{mode}_{route}_{month}_{year}.json"
        
        result_dir = os.path.join(self.results_dir, folder_name, mode)
        os.makedirs(result_dir, exist_ok=True)
        
        return os.path.join(result_dir, filename)
    
    def get_history_file_path(self, 
                              route: str, 
                              month: str, 
                              year: int, 
                              mode: str) -> str:
        """
        Путь к файлу истории.
        
        Args:
            route: Номер маршрута
            month: Название месяца
            year: Год
            mode: Режим симуляции
            
        Returns:
            Полный путь к файлу
        """
        folder_name = self.get_month_folder_name(month, year)
        filename = f"history_{mode}_{route}_{month}_{year}.json"
        
        hist_dir = os.path.join(self.history_dir, folder_name, mode)
        os.makedirs(hist_dir, exist_ok=True)
        
        return os.path.join(hist_dir, filename)
    
    def get_summary_report_path(self, 
                                 route: Optional[str], 
                                 month: str, 
                                 year: int, 
                                 mode: str,
                                 full_park: bool = False) -> str:
        """
        Путь к сводному отчету.
        
        Args:
            route: Номер маршрута (None если full_park=True)
            month: Название месяца
            year: Год
            mode: Режим симуляции
            full_park: Отчет по всему парку
            
        Returns:
            Полный путь к файлу
        """
        folder_name = self.get_month_folder_name(month, year)
        
        if full_park:
            filename = f"summary_report_{mode}_FULL_PARK_{month}_{year}.xlsx"
        else:
            filename = f"summary_report_{mode}_{route}_{month}_{year}.xlsx"
        
        report_dir = os.path.join(
            self.outputs_dir, "SUMMARY_REPORTS", folder_name, mode
        )
        os.makedirs(report_dir, exist_ok=True)
        
        return os.path.join(report_dir, filename)
    
    def get_schedule_book_path(self, 
                                route: Optional[str], 
                                month: str, 
                                year: int, 
                                mode: str,
                                full_park: bool = False) -> str:
        """
        Путь к книге расписаний.
        
        Args:
            route: Номер маршрута (None если full_park=True)
            month: Название месяца
            year: Год
            mode: Режим симуляции
            full_park: Книга по всему парку
            
        Returns:
            Полный путь к файлу
        """
        folder_name = self.get_month_folder_name(month, year)
        
        if full_park:
            filename = f"schedule_book_{mode}_FULL_PARK_{month}_{year}.xlsx"
        else:
            filename = f"schedule_book_{mode}_{route}_{month}_{year}.xlsx"
        
        book_dir = os.path.join(
            self.outputs_dir, "SCHEDULE_BOOKS", folder_name, mode
        )
        os.makedirs(book_dir, exist_ok=True)
        
        return os.path.join(book_dir, filename)
    
    def get_simulation_results_dir(self, month: str, year: int, mode: str) -> str:
        """
        Директория с результатами симуляции за месяц.
        
        Args:
            month: Название месяца
            year: Год
            mode: Режим симуляции
            
        Returns:
            Путь к директории
        """
        folder_name = self.get_month_folder_name(month, year)
        return os.path.join(self.results_dir, folder_name, mode)
    
    def ensure_directories(self):
        """Создает все необходимые директории."""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.outputs_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.history_dir, exist_ok=True)
