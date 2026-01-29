# Инструкция по установке Octotraher

## Установка через pip

### 1. Установка из локальной директории

Если вы находитесь в корневой директории проекта:

```bash
pip install .
```

Для установки в режиме разработки (editable mode), когда изменения в коде сразу доступны без переустановки:

```bash
pip install -e .
```

### 2. Установка из Git репозитория

Если проект размещен на GitHub или другом Git-хостинге:

**Для публичного репозитория:**
```bash
pip install git+https://github.com/AOKonovalov/Octotraher.git
```

**Для приватного репозитория:**

**Через HTTPS с токеном доступа (рекомендуется):**

1. **Создайте Personal Access Token на GitHub:**
   - Перейдите: https://github.com/settings/tokens
   - Нажмите "Generate new token" → "Generate new token (classic)"
   - Выберите права: `repo` (для доступа к приватным репозиториям)
   - Скопируйте токен (он показывается только один раз!)

2. **Установка через токен:**

   **Вариант А: Через переменную окружения (самый безопасный способ):**
   
   Windows PowerShell:
   ```powershell
   $env:GIT_TOKEN="{YOUR_TOKEN}"
   pip install git+https://$env:GIT_TOKEN@github.com/AOKonovalov/Octotraher.git
   ```
   
   Windows CMD:
   ```cmd
   set GIT_TOKEN={YOUR_TOKEN}
   pip install git+https://%GIT_TOKEN%@github.com/AOKonovalov/Octotraher.git
   ```
   
   Linux/Mac:
   ```bash
   export GIT_TOKEN="{YOUR_TOKEN}"
   pip install git+https://${GIT_TOKEN}@github.com/AOKonovalov/Octotraher.git
   ```

   **Вариант Б: Напрямую в команде (менее безопасно):**
   ```bash
   pip install git+https://{YOUR_TOKEN}@github.com/AOKonovalov/Octotraher.git
   ```
   ⚠️ **Внимание:** Токен может попасть в историю команд!

   **Вариант В: В requirements.txt (НЕ коммитьте файл с токеном!):**
   ```
   git+https://{YOUR_TOKEN}@github.com/AOKonovalov/Octotraher.git
   ```
   Лучше использовать переменную окружения в CI/CD или локально.

**Альтернатива: Локальная установка:**
```bash
git clone https://{YOUR_TOKEN}@github.com/AOKonovalov/Octotraher.git
cd Octotraher
pip install -e .
```

**Для конкретной ветки или тега:**
```bash
pip install git+ssh://git@github.com/AOKonovalov/Octotraher.git@branch-name
# или
pip install git+https://<YOUR_TOKEN>@github.com/AOKonovalov/Octotraher.git@branch-name
```

### 3. Установка из архива

1. Создайте архив проекта (или скачайте его)
2. Распакуйте архив
3. Перейдите в директорию проекта
4. Выполните:

```bash
pip install .
```

### 4. Установка из собранного дистрибутива

#### Создание дистрибутива:

```bash
python setup.py sdist
```

Это создаст файл `dist/octotraher-0.1.0.tar.gz`

#### Установка из дистрибутива:

```bash
pip install dist/octotraher-0.1.0.tar.gz
```

Или если файл находится в другом месте:

```bash
pip install /путь/к/файлу/octotraher-0.1.0.tar.gz
```

## Проверка установки

После установки проверьте, что библиотека установлена корректно:

```bash
python -c "import octotraher; print(octotraher.__version__)"
```

Или проверьте CLI команду:

```bash
octotraher --help
```

## Использование в Python

После установки вы можете использовать библиотеку в своих проектах:

```python
import octotraher.modules.telegram as telegram

scraper = telegram.TelegramChannelScraper('channelname')
for item in scraper.get_items():
    print(item)
```

## Публикация на PyPI (опционально)

Если вы хотите, чтобы другие могли устанавливать вашу библиотеку через `pip install octotraher`:

1. Создайте аккаунты на [PyPI](https://pypi.org) и [Test PyPI](https://test.pypi.org)

2. Установите необходимые инструменты:

```bash
pip install build twine
```

3. Соберите пакет:

```bash
python -m build
```

4. Сначала загрузите на Test PyPI (для тестирования):

```bash
python -m twine upload --repository testpypi dist/*
```

5. Если всё работает, загрузите на PyPI:

```bash
python -m twine upload dist/*
```

После публикации на PyPI любой сможет установить библиотеку командой:

```bash
pip install octotraher
```

## Требования

- Python 3.8 или выше
- Зависимости устанавливаются автоматически при установке пакета

## Устранение проблем

Если возникают проблемы с установкой:

1. Убедитесь, что используете правильную версию Python:
```bash
python --version
```

2. Обновите pip:
```bash
pip install --upgrade pip
```

3. Установите в виртуальном окружении (рекомендуется):
```bash
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
pip install .
```

