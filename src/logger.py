import logging
import sys
from pathlib import Path
from datetime import datetime

def setup_logger(name: str = __name__, level: str = "INFO") -> logging.Logger:
    """
    Настройка логгера с единообразным форматированием
    
    Args:
        name: Имя логгера (обычно __name__ модуля)
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    
    # Избегаем дублирования хендлеров
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, level.upper()))
    
    # Создаем директорию для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Форматтер с коротким именем файла
    class ShortNameFormatter(logging.Formatter):
        def format(self, record):
            # Если это __main__, берем имя файла из pathname
            if record.name == '__main__':
                import os
                filename = os.path.basename(record.pathname)
                record.short_name = filename.replace('.py', '')
            else:
                # Берем только последнюю часть имени модуля
                record.short_name = record.name.split('.')[-1]
            return super().format(record)
    
    formatter = ShortNameFormatter(
        fmt='%(asctime)s | %(levelname)s | %(short_name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Хендлер для файла
    file_handler = logging.FileHandler(
        log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Хендлер для консоли (только INFO и выше)
    # Проверяем, не интерактивный ли это файл
    if not name.endswith('manage_absences'):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger


def get_file_only_logger(name: str = None) -> logging.Logger:
    """Получить логгер, который пишет ТОЛЬКО в файл (для интерактивных скриптов)"""
    if name is None:
        # Получаем имя вызывающего модуля
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    logger = logging.getLogger(f"{name}_file_only")
    
    # Избегаем дублирования хендлеров
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Создаем директорию для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Форматтер с коротким именем файла
    class ShortNameFormatter(logging.Formatter):
        def format(self, record):
            if record.name.endswith('_file_only'):
                record.short_name = record.name.replace('_file_only', '').split('.')[-1]
            else:
                record.short_name = record.name.split('.')[-1]
            return super().format(record)
    
    formatter = ShortNameFormatter(
        fmt='%(asctime)s | %(levelname)s | %(short_name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # ТОЛЬКО хендлер для файла (без консоли)
    file_handler = logging.FileHandler(
        log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

# Удобные функции для быстрого использования
def get_logger(name: str = None) -> logging.Logger:
    """Получить логгер для модуля"""
    if name is None:
        # Получаем имя вызывающего модуля
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return setup_logger(name)


def get_file_only_logger(name: str = None) -> logging.Logger:
    """Получить логгер, который пишет ТОЛЬКО в файл (для интерактивных скриптов)"""
    if name is None:
        # Получаем имя вызывающего модуля
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    logger = logging.getLogger(f"{name}_file_only")
    
    # Избегаем дублирования хендлеров
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Создаем директорию для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Форматтер с коротким именем файла
    class ShortNameFormatter(logging.Formatter):
        def format(self, record):
            if record.name.endswith('_file_only'):
                record.short_name = record.name.replace('_file_only', '').split('.')[-1]
            else:
                record.short_name = record.name.split('.')[-1]
            return super().format(record)
    
    formatter = ShortNameFormatter(
        fmt='%(asctime)s | %(levelname)s | %(short_name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # ТОЛЬКО хендлер для файла (без консоли)
    file_handler = logging.FileHandler(
        log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger