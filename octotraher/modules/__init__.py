import pkgutil
import importlib


__all__ = []


def _import_modules():
	prefixLen = len(__name__) + 1
	for importer, moduleName, isPkg in pkgutil.iter_modules(__path__, prefix = f'{__name__}.'):
		assert not isPkg
		moduleNameWithoutPrefix = moduleName[prefixLen:]
		__all__.append(moduleNameWithoutPrefix)
		# Используем importlib вместо устаревшего find_module
		# Игнорируем ошибки импорта, если модуль требует дополнительные зависимости
		try:
			module = importlib.import_module(moduleName)
			globals()[moduleNameWithoutPrefix] = module
		except (ImportError, ModuleNotFoundError) as e:
			# Пропускаем модули, которые не могут быть загружены из-за отсутствующих зависимостей
			pass


_import_modules()
