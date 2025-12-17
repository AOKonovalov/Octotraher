"""
Тестовый файл для функции parse_telegram_channels (octotraher парсер)
"""
import json
import logging
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import octotraher.modules.telegram as telegram

def to_moscow_time(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    moscow_tz = timezone(timedelta(hours=3))
    dt_moscow = dt.astimezone(moscow_tz)
    return dt_moscow.replace(tzinfo=None)

def moscow_now() -> datetime:
    return to_moscow_time(datetime.now(timezone.utc))


# Импортируем утилиты
sys.path.append('.')


# Настройка логирования - только критичные ошибки
logging.basicConfig(
    level=logging.ERROR,  # Только критические ошибки
    format='%(levelname)s - %(message)s'  # Минимальный формат
)
logger = logging.getLogger(__name__)

# Отключаем все логи от сторонних библиотек
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('octotraher').setLevel(logging.CRITICAL)
logging.getLogger('octotraher.modules.telegram').setLevel(logging.CRITICAL)


def parse_telegram_channels(channels: List[str], limit: int = 10, time_minutes_filter: int = 30) -> List[dict]:
    """
    Парсер на octotraher – используется как запасной при падении Pyrogram
    """
    results: List[dict] = []
    
    for channel in channels:
        try:
            scraper = telegram.TelegramChannelScraper(channel)
            
            # Время для фильтрации (проверяем ДО обработки медиа)
            moscow_now_time = moscow_now()
            
            for i, msg in enumerate(scraper.get_items()):
                if limit is not None and i >= limit:
                    break
                
                # Проверяем время ДО обработки медиа (экономия времени)
                msg_date_for_check = msg.date
                if msg_date_for_check and msg_date_for_check.tzinfo is None:
                    msg_date_for_check = msg_date_for_check.replace(tzinfo=timezone.utc)
                msg_date_moscow = to_moscow_time(msg_date_for_check) if msg_date_for_check else None
                
                # Пропускаем старые сообщения ДО скачивания медиа
                if msg_date_moscow and (moscow_now_time - msg_date_moscow) > timedelta(minutes=time_minutes_filter):
                    continue  # Пропускаем это сообщение, не обрабатываем медиа
                
                # Извлечение message_id из URL
                # Формат URL: https://t.me/s/channel_name/123 или https://t.me/channel_name/123
                message_id = 0
                msg_url = getattr(msg, 'url', '')
                if msg_url:
                    try:
                        url_parts = msg_url.replace('https://t.me/s/', '').replace('https://t.me/', '').split('/')
                        if len(url_parts) >= 2:
                            message_id = int(url_parts[-1])
                    except (ValueError, IndexError):
                        pass  # Пропускаем, если не удалось извлечь message_id
                
                # Обработка медиа файлов - скачиваем только фото и видео в память как bytes
                # Результат: bytea[] - массив байтовых данных
                media_data = []
                media_urls_seen = set()  # Для дедупликации по URL
                
                # Основной способ: используем атрибут media из TelegramPost
                msg_media = getattr(msg, 'media', None)
                if msg_media is not None:
                    # Медиа может быть списком или одним элементом
                    media_items = msg_media if isinstance(msg_media, (list, tuple)) else [msg_media]
                    
                    # Сначала собираем уникальные URL
                    unique_media_urls = []
                    for media_item in media_items:
                        if media_item is None:
                            continue
                        
                        media_url = None
                        
                        # Обрабатываем только Photo и Video, остальное пропускаем
                        if isinstance(media_item, telegram.Photo):
                            media_url = media_item.url
                        elif isinstance(media_item, telegram.Video):
                            media_url = getattr(media_item, 'url', None)
                        else:
                            continue  # Пропускаем остальные типы
                        
                        # Дедупликация по URL
                        if media_url and media_url not in media_urls_seen:
                            media_urls_seen.add(media_url)
                            unique_media_urls.append(media_url)
                    
                    # Скачиваем только уникальные медиа (параллельно)
                    if unique_media_urls:
                        def download_media(media_url):
                            """Функция для скачивания одного медиа файла (макс. 5 МБ)"""
                            max_retries = 2
                            MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 МБ в байтах
                            
                            for attempt in range(max_retries + 1):
                                try:
                                    # Небольшая случайная задержка перед запросом (0-0.5 сек) для снижения нагрузки
                                    if attempt == 0:
                                        time.sleep(0.1 * (hash(media_url) % 5))  # 0-0.4 сек случайная задержка
                                    
                                    response = requests.get(media_url, timeout=15)  # Уменьшил таймаут до 15 сек
                                    response.raise_for_status()
                                    
                                    # Размер файла из заголовка (если есть)
                                    content_length = response.headers.get('Content-Length')
                                    file_size = int(content_length) if content_length else None
                                    
                                    # Проверяем размер ДО скачивания
                                    if file_size and file_size > MAX_FILE_SIZE:
                                        return None
                                    
                                    # Скачиваем файл в память
                                    media_bytes = response.content  # bytes
                                    
                                    # Проверяем реальный размер после скачивания
                                    if len(media_bytes) > MAX_FILE_SIZE:
                                        return None
                                    
                                    return media_bytes
                                except requests.exceptions.HTTPError as e:
                                    # Для 500/503 ошибок делаем повторную попытку
                                    if e.response.status_code in (500, 503) and attempt < max_retries:
                                        time.sleep(0.5)  # Небольшая задержка перед повтором
                                        continue
                                    # Для других ошибок - просто пропускаем
                                    return None
                                except Exception:
                                    # Пропускаем файл при любой ошибке
                                    return None
                            return None
                        
                        # Параллельная загрузка медиа (до 5 потоков одновременно, чтобы не получить бан)
                        # Медиа скачиваются с CDN Telegram, но все равно нужно быть осторожным
                        with ThreadPoolExecutor(max_workers=5) as executor:
                            future_to_url = {executor.submit(download_media, url): url for url in unique_media_urls}
                            for future in as_completed(future_to_url):
                                media_bytes = future.result()
                                if media_bytes:
                                    media_data.append(media_bytes)  # Добавляем в массив bytes
                
                # Извлечение views (IntWithGranularity)
                views = 0
                if hasattr(msg, 'views') and msg.views is not None:
                    try:
                        views = int(msg.views)
                    except (ValueError, TypeError):
                        views = 0
                
                # Извлечение реакций из TelegramPost
                reactions = 0
                msg_reactions = getattr(msg, 'reactions', None)
                if msg_reactions is not None:
                    reactions = int(msg_reactions)
                
                # Комментарии и репосты пока недоступны через публичный API
                comments = 0
                reposts = 0
                
                normalized_url = msg_url.replace('https://t.me/s/', 'https://t.me/') if msg_url else ''
                
                # Убеждаемся, что msg.date имеет timezone перед преобразованием
                msg_date_for_db = msg.date
                if msg_date_for_db and msg_date_for_db.tzinfo is None:
                    msg_date_for_db = msg_date_for_db.replace(tzinfo=timezone.utc)
                
                results.append({
                    'source': normalized_url,
                    'channel_id': 0,  # Можно извлечь из channel, если нужно
                    'message_id': message_id,
                    'message_text': getattr(msg, 'content', None) or '',
                    'title': '',
                    'reactions': reactions,  # Пока 0, нужно парсить HTML
                    'views': views,
                    'comments': comments,  # Пока 0, нужно парсить HTML
                    'reposts': reposts,  # Пока 0, нужно парсить HTML
                    'date': to_moscow_time(msg_date_for_db),
                    'parsed_time': moscow_now(),
                    'media': media_data if media_data else None,  # bytea[] - массив байтовых данных
                    # Дополнительные поля, если нужны:
                    'mentions': getattr(msg, 'mentions', None) or [],
                    'hashtags': getattr(msg, 'hashtags', None) or [],
                    # 'outlinks' убраны - не нужны
                    'forwarded_from': getattr(getattr(msg, 'forwarded', None), 'username', None) if hasattr(msg, 'forwarded') and msg.forwarded else None,
                    'forwarded_url': getattr(msg, 'forwardedUrl', None),
                    'link_preview': {
                        'href': getattr(msg.linkPreview, 'href', None),
                        'title': getattr(msg.linkPreview, 'title', None),
                        'siteName': getattr(msg.linkPreview, 'siteName', None),
                        'description': getattr(msg.linkPreview, 'description', None),
                        'image': getattr(msg.linkPreview, 'image', None)
                    } if hasattr(msg, 'linkPreview') and msg.linkPreview else None
                })
        except Exception:
            # Пропускаем канал без публичных постов (без логирования)
            continue
    
    # Фильтруем по времени (дополнительная проверка на всякий случай)
    # Основная фильтрация уже выполнена ДО скачивания медиа (строка 54)
    moscow_now_time = moscow_now()
    results = [
        item for item in results
        if item['date'] and (moscow_now_time - item['date']) <= timedelta(minutes=time_minutes_filter)
    ]
    
    return results


if __name__ == "__main__":
    # Список каналов для тестирования (заданы внутри файла)
    test_channels = [
        # 'e1_news', 'zloy_ekb', 'center_ekat', 
        # 'incekb', 'kudaekb', 'SvetEKB',
        # 'EkatskoeChtivo', 'ekaterinburg_smi', 'inburg', 
        # 'ekattop', 'zhest_ekat', 'momenty_ekb', 
        # 'ekb4tv', 'RU66RU', 'ekat01', 
        # 'ekbkoroche', 'ektbnews',

        # 'ftsec', 'addmeto', 'abulaphia',
        # 'seeallochnaya', 'ai_newz', 'denissexy',
        # 'ppprompt', 'strangedalle', 'nn_for_science',
        # 'GreenNeuralRobots', 'cgevent', 'hiaimedia',
        # 'whackdoor', 'vcnews', 'Theedinorogblog'
        # Добавьте другие каналы для тестирования
        "news_74ru", "nashchelyabinsk", "chelyabinsk_smi",
    "url_mash", "chelyabushka",
    "newschelyaba", "ACityThatSmog", "nashregion74",
    "novosti_chelyab", "chelyabinsk01", "chp174"
    "achnov", "chpmiass",
    "afishamgn", "toporlive", "gumvd74",
    "kopvtm", "shot_shot", "ugibdd74",
    "cheliabinsktop", "bazabazon",
    "url_mash", "bbbreaking",
    "news_74ru", "PogonyGalstuky",
    "miassplombir",
    "ACityThatSmog",
    "novosti_chelyab",
    "newschelyaba",
    "chelyabinsk01",
    "monitoring_74",
    "eanchel",
    "go_ozersk",
    "chelyabinsk_smi",
    "odinobl",
    "cheltodayru",
    "podslushano_174",
    "pravdaurfo",
    "skotobaza_chel",
    "camel74",
    "steel_magnitogorsk",
    "verstovinfo"
    ]
    
    # Параметры парсинга
    limit = 10  # Лимит сообщений на канал
    time_minutes_filter = 30  # Фильтр по времени (минуты)
    
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ parse_telegram_channels")
    print("=" * 80)
    print(f"Каналы: {test_channels}")
    print(f'кол-во {len(test_channels)}')
    print(f"Лимит: {limit} сообщений на канал")
    print(f"Фильтр времени: {time_minutes_filter} минут")
    print("=" * 80)
    print()
    
    try:
        start_time = time.time()
        results = parse_telegram_channels(test_channels, limit=limit, time_minutes_filter=time_minutes_filter)
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        print(f"\n✅ Парсинг завершен успешно!")
        print(f"📊 Всего получено сообщений: {len(results)}")
        print(f"⏱️  Время парсинга: {elapsed_time:.2f} секунд ({elapsed_time/60:.2f} минут)")
        print()
        
        # # Выводим результаты
        # for idx, result in enumerate(results, 1):
        #     print(f"\n{'='*80}")
        #     print(f"Сообщение {idx} из {len(results)}")
        #     print(f"{'='*80}")
        #     print(f"📎 Источник: {result.get('source')}")
        #     print(f"🆔 Message ID: {result.get('message_id')}")
        #     print(f"📅 Дата: {result.get('date')}")
        #     print(f"⏰ Время парсинга: {result.get('parsed_time')}")
        #     print()
        #     print(f"📊 Статистика:")
        #     print(f"   👁️  Просмотры: {result.get('views')}")
        #     print(f"   ❤️  Реакции: {result.get('reactions')}")
        #     print(f"   💬 Комментарии: {result.get('comments')}")
        #     print(f"   🔄 Репосты: {result.get('reposts')}")
        #     print()
            
        #     # Текст сообщения
        #     text = result.get('message_text', '')
        #     if text:
        #         text_preview = text[:200] + "..." if len(text) > 200 else text
        #         print(f"📝 Текст сообщения:")
        #         print(f"   {text_preview}")
        #         print()
            
        #     # Медиа (bytea[])
        #     if result.get('media'):
        #         media_array = result.get('media', [])
        #         print(f"🖼️  Медиа файлов: {len(media_array)}")
        #         for media_idx, media_bytes in enumerate(media_array, 1):
        #             data_size = len(media_bytes) if media_bytes else 0
        #             print(f"   [{media_idx}] Размер: {data_size} bytes ({data_size / 1024:.2f} KB)")
        #     else:
        #         print("🖼️  Медиа: нет")
        #     print()
        
        print("\n" + "=" * 80)
        print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Ошибка при парсинге: {e}")
        import traceback
        traceback.print_exc()

