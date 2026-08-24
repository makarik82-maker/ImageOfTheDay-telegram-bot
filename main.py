import os
import sys
import tempfile
import random
import logging
import asyncio
import time
from datetime import datetime
import requests
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

# Переменные окружения
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# Все доступные категории Unsplash (циклически меняются)
CATEGORIES = [
    'nature landscape beautiful',
    'animals wildlife birds',
    'space planet earth astronomy',
    'sunset sunrise sky',
    'mountain forest water',
    'ocean sea beach',
    'flowers garden spring',
    'winter snow ice',
    'autumn fall leaves',
    'city urban architecture',
    'food cooking delicious',
    'travel adventure journey'
]

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
            desc = f"Beautiful photo: {query}"
        
        caption = f"🌿 <b>Image of the Day</b>\n\n{desc}\n\n📸 {photographer}\n🌐 Unsplash"
        return {'url': img_url, 'caption': caption[:1024]}
    except Exception as e:
        logger.error(f"❌ Unsplash ({query}): {e}")
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
        
        # Скачиваем изображение с проверками и увеличенным временем ожидания
        max_download_attempts = 5
        for attempt in range(max_download_attempts):
            try:
                r = requests.get(content['url'], timeout=120, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                
                if r.status_code == 429:
                    wait_time = 10 * (attempt + 1)
                    logger.warning(f"⚠️ 429 Too Many Requests. Ждем {wait_time} секунд...")
                    time.sleep(wait_time)
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
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Превышено время ожидания при загрузке (попытка {attempt + 1})")
                if attempt < max_download_attempts - 1:
                    time.sleep(5)
                    continue
                else:
                    logger.error(" Не удалось скачать изображение: таймаут")
                    return False
            except Exception as e:
                logger.error(f"❌ Ошибка при загрузке: {e}")
                return False
        else:
            logger.error("❌ Не удалось скачать изображение после всех попыток")
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
                logger.info(f" Попытка отправки #{send_attempt + 1}...")
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
def get_last_category_index():
    """Получить индекс последней использованной категории"""
    github_env = os.getenv('GITHUB_ENV')
    if github_env and os.path.exists(github_env):
        try:
            with open(github_env, 'r') as f:
                for line in f:
                    if line.startswith('LAST_CATEGORY_INDEX='):
                        return int(line.strip().split('=')[1])
        except Exception:
            pass
    return -1  # Если не найдено, начинаем с первой категории


def save_category_index(index):
    """Сохранить индекс текущей категории"""
    github_env = os.getenv('GITHUB_ENV')
    if github_env:
        with open(github_env, 'a') as f:
            f.write(f"LAST_CATEGORY_INDEX={index}\n")
        logger.info(f"✅ Сохранен индекс категории: {index}")


def main():
    logger.info("🚀 Запуск Image of the Day бота")
    
    if not all([BOT_TOKEN, CHANNEL_ID]):
        logger.error("❌ Не все переменные окружения установлены (проверьте TELEGRAM_BOT_TOKEN и TELEGRAM_CHANNEL_ID)")
        return False
    
    # Получаем индекс последней использованной категории и выбираем следующую
    last_index = get_last_category_index()
    current_index = (last_index + 1) % len(CATEGORIES)
    current_category = CATEGORIES[current_index]
    
    logger.info(f"🎯 Категория #{current_index + 1}/{len(CATEGORIES)}: {current_category}")
    logger.info(f"📊 Последняя категория была #{last_index + 1}")
    
    content = None
    
    # Пробуем получить изображение из текущей категории
    content = get_unsplash_image(current_category)
    
    # Если не получилось, пробуем следующие категории по порядку
    if not content:
        logger.warning("⚠️ Не удалось получить фото, пробуем следующие категории...")
        
        # Пробуем все остальные категории по кругу
        for i in range(1, len(CATEGORIES)):
            next_index = (current_index + i) % len(CATEGORIES)
            next_category = CATEGORIES[next_index]
            
            logger.info(f"🔄 Пробуем категорию #{next_index + 1}: {next_category}")
            content = get_unsplash_image(next_category)
            
            if content:
                logger.info(f"✅ Успешно получено из категории #{next_index + 1}")
                current_index = next_index
                break
    
    if not content:
        logger.error("❌ Не удалось получить изображение ни из одной категории")
        return False
    
    # Отправляем в Telegram
    if send_image(content):
        today = datetime.now().strftime('%Y-%m-%d')
        save_category_index(current_index)
        
        # Также сохраняем дату для отслеживания
        with open(os.getenv('GITHUB_ENV', '/dev/null'), 'a') as f:
            f.write(f"LAST_IMAGE_DATE={today}\n")
        
        logger.info(f" Дата публикации: {today}")
        return True
    
    return False


if __name__ == "__main__":
    success = main()
    # Возвращаем код завершения для GitHub Actions (0 = успех, 1 = ошибка)
    sys.exit(0 if success else 1)
