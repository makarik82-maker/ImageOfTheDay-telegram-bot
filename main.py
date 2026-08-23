import os
import sys
import tempfile
import random
import logging
import asyncio
import time
from datetime import datetime
import requests
from deep_translator import GoogleTranslator
from telegram import Bot
from telegram.request import HTTPXRequest

# ==============================================================================
# НАСТРОЙКИ И ЛОГИРОВАНИЕ
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация переводчика
translator = GoogleTranslator(source='auto', target='ru')

# Переменные окружения (имена должны совпадать с Secrets в GitHub Actions)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# Доступные источники
SOURCES = ['unsplash_nature', 'unsplash_animals', 'unsplash_space', 'wikimedia', 'nasa']

# ==============================================================================
# ФУНКЦИИ ПОЛУЧЕНИЯ ИЗОБРАЖЕНИЙ
# ==============================================================================
def get_unsplash_image(query):
    """Получить случайное фото с Unsplash"""
    try:
        headers = {'Authorization': f'Client-ID {UNSPLASH_KEY}'} if UNSPLASH_KEY else {}
        url = f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape"
        
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        # Unsplash API может вернуть список или один объект
        if isinstance(data, list):
            data = data[0]
        
        img_url = data['urls']['regular']
        desc = data.get('description', '') or data.get('alt_description', '')
        photographer = data['user']['name']
        
        # Фильтрация мусорных описаний и текстов ошибок сервера
        error_keywords = ['error', '500', "that's an error", 'server error', '!!']
        if not desc or any(keyword in desc.lower() for keyword in error_keywords):
            desc_ru = f"Красивое фото: {query}"
        else:
            try:
                desc_ru = translator.translate(desc)
            except Exception:
                desc_ru = desc
        
        caption = f"🌿 <b>Image of the Day</b>\n\n{desc_ru}\n\n📸 {photographer}\n🌐 Unsplash"
        return {'url': img_url, 'caption': caption[:1024]}
    except Exception as e:
        logger.error(f"❌ Unsplash ({query}): {e}")
        return None


def get_wikimedia_featured():
    """Получить случайное фото с Wikimedia Commons"""
    try:
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'generator': 'random',
            'grnnamespace': 6,  # Namespace для файлов
            'grnlimit': 10,
            'prop': 'imageinfo',
            'iiprop': 'url',
            'redirects': ''
        }
        
        r = requests.get(url, params=params, headers={'User-Agent': 'ImageOfTheDayBot/1.0'}, timeout=30)
        r.raise_for_status()
        pages = r.json().get('query', {}).get('pages', {})
        
        for page_id, page in pages.items():
            if 'imageinfo' in page:
                img_info = page['imageinfo'][0]
                img_url = img_info['url']
                
                # Проверяем, что это изображение
                if any(ext in img_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    title = page['title'].replace('File:', '').replace('_', ' ')
                    desc = f"Избранное фото: {title}"
                    try:
                        desc_ru = translator.translate(desc)
                    except Exception:
                        desc_ru = desc
                    
                    caption = f"🌍 <b>Image of the Day</b>\n\n{desc_ru}\n\n🌐 Wikimedia Commons"
                    return {'url': img_url, 'caption': caption[:1024]}
        return None
    except Exception as e:
        logger.error(f"❌ Wikimedia: {e}")
        return None


def get_national_park_image():
    """Получить фото из архива NASA"""
    try:
        url = "https://images-api.nasa.gov/search"
        params = {
            'q': random.choice(['earth', 'nature', 'wildlife', 'forest', 'ocean', 'mountain', 'galaxy']),
            'media_type': 'image',
            'page_size': 100
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        items = data.get('collection', {}).get('items', [])
        if items:
            item = random.choice(items)
            links = item.get('links', [])
            if not links:
                return None
                
            img_url = links[0].get('href')
            meta = item.get('data', [{}])[0]
            title = meta.get('title', 'Nature')
            desc = meta.get('description', '')
            
            if img_url:
                try:
                    title_ru = translator.translate(title)
                    desc_ru = translator.translate(desc[:200]) if desc else ''
                except Exception:
                    title_ru, desc_ru = title, desc
                
                caption = f"🌎 <b>Image of the Day</b>\n\n<b>{title_ru}</b>\n\n{desc_ru}\n\n🌐 NASA"
                return {'url': img_url, 'caption': caption[:1024]}
        return None
    except Exception as e:
        logger.error(f"❌ NASA: {e}")
        return None

# ==============================================================================
# ФУНКЦИЯ ОТПРАВКИ С УВЕЛИЧЕННЫМИ ТАЙМАУТАМИ И RETRY
# ==============================================================================
def send_image(content):
    """Отправить фото в Telegram с увеличенным таймаутом и повторными попытками"""
    path = None
    try:
        # Увеличиваем таймауты для HTTP-запросов бота
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=30.0,
            read_timeout=60.0,
            write_timeout=60.0,
            pool_timeout=30.0
        )
        
        bot = Bot(token=BOT_TOKEN, request=request)
        logger.info(f"📥 Скачивание изображения: {content['url'][:60]}...")
        
        # Скачиваем изображение с проверками
        for attempt in range(3):
            r = requests.get(content['url'], timeout=60, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            
            if r.status_code == 429:
                logger.warning("⚠️ 429 Too Many Requests. Ждем 5 секунд...")
                time.sleep(5)
                continue
            
            # Проверка, что сервер вернул именно изображение, а не HTML-страницу ошибки
            content_type = r.headers.get('Content-Type', '').lower()
            if not content_type.startswith('image/'):
                logger.error(f"❌ По ссылке вернулся не изображение, а: {content_type}")
                return False
            
            # Проверка размера файла (страницы ошибок обычно весят < 5 КБ)
            if len(r.content) < 5000:
                logger.error("❌ Размер файла слишком мал (< 5 КБ), вероятно это страница ошибки сервера")
                return False
                
            r.raise_for_status()
            break
        else:
            logger.error("❌ Не удалось скачать изображение после 3 попыток")
            return False
        
        # Определяем расширение файла на основе реального Content-Type
        ext = '.jpg'
        if 'png' in content_type:
            ext = '.png'
        elif 'gif' in content_type:
            ext = '.gif'
        elif 'webp' in content_type:
            ext = '.webp'
            
        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
            f.write(r.content)
            path = f.name
        
        logger.info("✅ Файл скачан и проверен, отправка в Telegram...")
        
        # Отправка с повторными попытками
        max_send_attempts = 3
        for send_attempt in range(max_send_attempts):
            try:
                logger.info(f"🔄 Попытка отправки #{send_attempt + 1}...")
                with open(path, 'rb') as photo:
                    asyncio.run(bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=photo,
                        caption=content['caption'],
                        parse_mode='HTML',
                        read_timeout=60,
                        write_timeout=60,
                        connect_timeout=30,
                        pool_timeout=30
                    ))
                logger.info("✅ Фото успешно отправлено!")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Попытка #{send_attempt + 1} не удалась: {e}")
                if send_attempt < max_send_attempts - 1:
                    wait_time = 5 * (send_attempt + 1)
                    logger.info(f"⏳ Ждем {wait_time} секунд перед следующей попыткой...")
                    time.sleep(wait_time)
        
        logger.error("❌ Не удалось отправить фото после всех попыток")
        return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False
    finally:
        # Гарантированная очистка временного файла
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И MAIN
# ==============================================================================
def set_github_variable(name, value):
    """Обновление переменной для GitHub Actions (если запускается там)"""
    github_env = os.getenv('GITHUB_ENV')
    if github_env:
        with open(github_env, 'a') as f:
            f.write(f"{name}={value}\n")
        logger.info(f"✅ Переменная {name} обновлена в GitHub Actions")
    else:
        logger.info(f"ℹ️ Локальный режим: переменная {name}={value}")


def main():
    logger.info("🚀 Запуск Image of the Day бота")
    
    if not all([BOT_TOKEN, CHANNEL_ID]):
        logger.error("❌ Не все переменные окружения установлены (проверьте TELEGRAM_BOT_TOKEN и TELEGRAM_CHANNEL_ID)")
        return False
    
    # Выбираем случайный основной источник
    source = random.choice(SOURCES)
    logger.info(f"🎯 Основной источник: {source}")
    
    content = None
    
    # Получаем изображение
    if source == 'unsplash_nature':
        content = get_unsplash_image('nature landscape beautiful')
    elif source == 'unsplash_animals':
        content = get_unsplash_image('animals wildlife birds')
    elif source == 'unsplash_space':
        content = get_unsplash_image('space planet earth astronomy')
    elif source == 'wikimedia':
        content = get_wikimedia_featured()
    elif source == 'nasa':
        content = get_national_park_image()
    
    # Улучшенная логика fallback (запасных вариантов)
    if not content:
        logger.warning("️ Не удалось получить фото из основного источника, пробуем запасные...")
        fallback_sources = ['nasa', 'wikimedia', 'unsplash_nature']
        if source in fallback_sources:
            fallback_sources.remove(source)
        
        for fallback in fallback_sources:
            logger.info(f"🔄 Пробуем запасной источник: {fallback}")
            if fallback == 'nasa':
                content = get_national_park_image()
            elif fallback == 'wikimedia':
                content = get_wikimedia_featured()
            elif fallback == 'unsplash_nature':
                content = get_unsplash_image('nature landscape')
            
            if content:
                logger.info(f"✅ Успешно получено из запасного источника: {fallback}")
                break
    
    if not content:
        logger.error("❌ Не удалось получить изображение ни из одного источника")
        return False
    
    # Отправляем в Telegram
    if send_image(content):
        today = datetime.now().strftime('%Y-%m-%d')
        set_github_variable("LAST_IMAGE_DATE", today)
        return True
    
    return False


if __name__ == "__main__":
    success = main()
    # Возвращаем код завершения для GitHub Actions (0 = успех, 1 = ошибка)
    sys.exit(0 if success else 1)
