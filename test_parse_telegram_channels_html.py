"""
Тестовый файл для парсинга каналов Telegram с сохранением HTML-разметки (форматирование текста).
Использует get_message_content_html и TelegramChannelScraper(..., content_as_html=True).
"""
import json
import logging
import sys
import time
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import List, Optional

# Проверка версии Python
python_version = sys.version_info
print(f"🐍 Python версия: {python_version.major}.{python_version.minor}.{python_version.micro}")
if python_version.major == 3 and python_version.minor >= 8:
    print("✅ Версия Python подходит")
else:
    print(f"❌ Неподдерживаемая версия Python: {python_version.major}.{python_version.minor}")
    sys.exit(1)
print()

# Проверка импорта octotraher и telegram
try:
    import octotraher.modules.telegram as telegram
    from octotraher.modules.telegram import get_message_content_html
    print(f"✅ Модуль telegram импортирован, get_message_content_html доступна")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
print()

def to_moscow_time(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    moscow_tz = timezone(timedelta(hours=3))
    return dt.astimezone(moscow_tz).replace(tzinfo=None)

def moscow_now() -> datetime:
    return to_moscow_time(datetime.now(timezone.utc))

# Настройка логирования
logging.basicConfig(
    level=logging.ERROR,
    format='%(levelname)s - %(message)s'
)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('octotraher').setLevel(logging.CRITICAL)
logging.getLogger('octotraher.modules.telegram').setLevel(logging.CRITICAL)


def parse_telegram_channels_html(
    channels: List[str],
    limit: int = 10,
    time_minutes_filter: int = 30
) -> List[dict]:
    """
    Парсер каналов с сохранением HTML в тексте сообщений (жирный, курсив, ссылки, код и т.д.).
    Использует TelegramChannelScraper(..., content_as_html=True).
    """
    results: List[dict] = []

    for channel_idx, channel in enumerate(channels, 1):
        try:
            print(f"📡 Обработка канала {channel_idx}/{len(channels)}: {channel}")
            scraper = telegram.TelegramChannelScraper(channel, content_as_html=True)

            moscow_now_time = moscow_now()

            for i, msg in enumerate(scraper.get_items()):
                if limit is not None and i >= limit:
                    break

                msg_date_for_check = msg.date
                if msg_date_for_check and msg_date_for_check.tzinfo is None:
                    msg_date_for_check = msg_date_for_check.replace(tzinfo=timezone.utc)
                msg_date_moscow = to_moscow_time(msg_date_for_check) if msg_date_for_check else None

                if msg_date_moscow and (moscow_now_time - msg_date_moscow) > timedelta(minutes=time_minutes_filter):
                    continue

                message_id = 0
                msg_url = getattr(msg, 'url', '')
                if msg_url:
                    try:
                        url_parts = msg_url.replace('https://t.me/s/', '').replace('https://t.me/', '').split('/')
                        if len(url_parts) >= 2:
                            message_id = int(url_parts[-1])
                    except (ValueError, IndexError):
                        pass

                # Медиа — по желанию можно оставить как в test_parse_telegram_channels.py
                # Здесь для краткости не скачиваем медиа, только проверяем HTML-контент
                media_data = []

                views = 0
                if hasattr(msg, 'views') and msg.views is not None:
                    try:
                        views = int(msg.views)
                    except (ValueError, TypeError):
                        views = 0

                reactions = 0
                if getattr(msg, 'reactions', None) is not None:
                    reactions = int(msg.reactions)

                normalized_url = msg_url.replace('https://t.me/s/', 'https://t.me/') if msg_url else ''
                msg_date_for_db = msg.date
                if msg_date_for_db and msg_date_for_db.tzinfo is None:
                    msg_date_for_db = msg_date_for_db.replace(tzinfo=timezone.utc)

                # message_text здесь содержит HTML (теги сохранены)
                message_html = getattr(msg, 'content', None) or ''

                results.append({
                    'source': normalized_url,
                    'channel_id': 0,
                    'message_id': message_id,
                    'message_text': message_html,  # HTML с тегами
                    'title': '',
                    'reactions': reactions,
                    'views': views,
                    'comments': 0,
                    'reposts': 0,
                    'date': to_moscow_time(msg_date_for_db),
                    'parsed_time': moscow_now(),
                    'media': media_data if media_data else None,
                    'mentions': getattr(msg, 'mentions', None) or [],
                    'hashtags': getattr(msg, 'hashtags', None) or [],
                    'forwarded_from': getattr(getattr(msg, 'forwarded', None), 'username', None) if getattr(msg, 'forwarded', None) else None,
                    'forwarded_url': getattr(msg, 'forwardedUrl', None),
                    'link_preview': {
                        'href': getattr(msg.linkPreview, 'href', None),
                        'title': getattr(msg.linkPreview, 'title', None),
                        'siteName': getattr(msg.linkPreview, 'siteName', None),
                        'description': getattr(msg.linkPreview, 'description', None),
                        'image': getattr(msg.linkPreview, 'image', None)
                    } if hasattr(msg, 'linkPreview') and msg.linkPreview else None
                })
        except KeyboardInterrupt:
            print(f"\n⚠️  Прервано пользователем при обработке канала: {channel}")
            raise
        except Exception as e:
            error_type = type(e).__name__
            if "ScraperException" in error_type or "status code" in str(e).lower():
                print(f"   ⚠️  Канал {channel}: нет публичных постов или недоступен")
            else:
                print(f"   ⚠️  Канал {channel}: ошибка ({error_type}): {str(e)[:100]}")
            continue

    moscow_now_time = moscow_now()
    results = [
        item for item in results
        if item['date'] and (moscow_now_time - item['date']) <= timedelta(minutes=time_minutes_filter)
    ]
    return results


def has_html_tags(text: str) -> bool:
    """Проверяет, есть ли в тексте HTML-теги."""
    if not text:
        return False
    return bool(re.search(r'<[a-zA-Z/][^>]*>', text))


if __name__ == "__main__":
    test_channels = [
        "news_74ru",
        "nashchelyabinsk",
        "chelyabinsk_smi",
        "url_mash",
    ]

    limit = 5
    time_minutes_filter = 60

    print("=" * 80)
    print("ТЕСТИРОВАНИЕ parse_telegram_channels_html (контент с сохранением HTML)")
    print("=" * 80)
    print(f"📋 Каналов: {len(test_channels)}")
    print(f"📊 Лимит: {limit} сообщений на канал")
    print(f"⏰ Фильтр времени: {time_minutes_filter} минут")
    print("=" * 80)
    print()

    try:
        start_time = time.time()
        results = parse_telegram_channels_html(
            test_channels,
            limit=limit,
            time_minutes_filter=time_minutes_filter
        )
        end_time = time.time()
        elapsed_time = end_time - start_time

        print(f"\n✅ Парсинг завершен успешно!")
        print(f"📊 Всего сообщений: {len(results)}")
        print(f"⏱️  Время: {elapsed_time:.2f} сек")
        print()

        # Проверка: у скольких сообщений в контенте есть HTML-теги
        with_tags = sum(1 for r in results if has_html_tags(r.get('message_text', '')))
        print(f"📝 Сообщений с HTML-тегами в тексте: {with_tags} из {len(results)}")
        print()

        # Вывод нескольких примеров (превью HTML-контента)
        for idx, result in enumerate(results[:3], 1):
            print(f"{'─' * 80}")
            print(f"Сообщение {idx}")
            print(f"📎 Источник: {result.get('source')}")
            print(f"🆔 Message ID: {result.get('message_id')}")
            print(f"📅 Дата: {result.get('date')}")
            text = result.get('message_text', '')
            if text:
                preview = text[:300] + "..." if len(text) > 300 else text
                print(f"📝 Текст (HTML): {preview!r}")
                print(f"   Есть теги: {has_html_tags(text)}")
            print()

        print("=" * 80)
        print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        print("=" * 80)

    except KeyboardInterrupt:
        print(f"\n⚠️  Парсинг прерван (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
