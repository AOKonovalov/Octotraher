import importlib
import importlib.util
import os
from pathlib import Path


__all__ = []


def _import_modules():
	"""Импортирует все модули из директории modules, совместимо с Python 3.12+"""
	# Получаем путь к директории модулей
	modules_dir = Path(__file__).parent
	prefixLen = len(__name__) + 1
	
	# Сканируем директорию и находим все .py файлы (кроме __init__.py)
	for module_file in modules_dir.glob('*.py'):
		module_name = module_file.stem
		if module_name == '__init__':
			continue
		
		module_full_name = f'{__name__}.{module_name}'
		module_name_without_prefix = module_full_name[prefixLen:]
		
		__all__.append(module_name_without_prefix)
		
		# Используем importlib для безопасного импорта (совместимо с Python 3.12+)
		try:
			module = importlib.import_module(module_full_name)
			globals()[module_name_without_prefix] = module
		except (ImportError, ModuleNotFoundError):
			# Пропускаем модули, которые не могут быть загружены из-за отсутствующих зависимостей
			pass


_import_modules()
