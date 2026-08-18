import os, random, requests, logging, asyncio, tempfile
from telegram import Bot
from deep_translator import GoogleTranslator
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
UNSPLASH_KEY = os.getenv('UNSPLASH_ACCESS_KEY')  # Получите на https://unsplash.com/developers

GH_TOKEN = os.getenv('GITHUB_TOKEN')
GH_REPO = os.getenv('GITHUB_REPOSITORY')

translator = GoogleTranslator(source='auto', target='ru')

# Источники изображений
SOURCES = ['unsplash_nature', 'unsplash_animals', 'unsplash_space', 'wikimedia']

def get_unsplash_image(query):
    """Получить случайное фото с Unsplash"""
    try:
        headers = {'Authorization': f'Client-ID {UNSPLASH_KEY}'} if UNSPLASH_KEY else {}
        url = f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape&count=1"
        if headers:
            r = requests.get(url, headers=headers, timeout=30)
        else:
            # Fallback без ключа (ограничено 50 запросов/час)
            r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()[0] if isinstance(r.json(), list) else r.json()
        
        img_url = data['urls']['regular']
        desc = data.get('description', '') or data.get('alt_description', '')
        photographer = data['user']['name']
        
        if desc:
            try:
                desc_ru = translator.translate(desc)
            except:
                desc_ru = desc
        else:
            desc_ru = f"Красивое фото: {query}"
        
        caption = f"🌿 <b>Image of the Day</b>\n\n{desc_ru}\n\n📸 {photographer}\n🌐 Unsplash"
        return {'url': img_url, 'caption': caption[:1024]}
    except Exception as e:
        logger.error(f"❌ Unsplash ({query}): {e}")
        return None

def get_wikimedia_featured():
    """Получить избранное фото с Wikimedia Commons"""
    try:
        # Запрос к API Wikimedia
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'generator': 'random',
            'grnnamespace': 6,  # Namespace для файлов
            'grnlimit': 10,
            'prop': 'imageinfo|info',
            'iiprop': 'url|extmetadata',
            'iinprop': 'url',
            'redirects': ''
        }
        
        r = requests.get(url, params=params, headers={'User-Agent': 'ImageBot/1.0'}, timeout=30)
        r.raise_for_status()
        pages = r.json()['query']['pages']
        
        for page_id, page in pages.items():
            if 'imageinfo' in page:
                img_info = page['imageinfo'][0]
                img_url = img_info['url']
                
                # Проверяем, что это изображение (не звук/видео)
                if any(ext in img_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                    title = page['title'].replace('File:', '').replace('_', ' ')
                    desc = f"Избранное фото Wikimedia: {title}"
                    try:
                        desc_ru = translator.translate(desc)
                    except:
                        desc_ru = desc
                    
                    caption = f"🌍 <b>Image of the Day</b>\n\n{desc_ru}\n\n🌐 Wikimedia Commons"
                    return {'url': img_url, 'caption': caption[:1024]}
        
        return None
    except Exception as e:
        logger.error(f"❌ Wikimedia: {e}")
        return None

def get_national_park_image():
    """Получить фото из национальных парков (NASA/NPS)"""
    try:
        # Используем NASA API для красивых фото природы
        url = "https://images-api.nasa.gov/search"
        params = {
            'q': random.choice(['earth', 'nature', 'wildlife', 'forest', 'ocean', 'mountain']),
            'media_type': 'image',
            'page_size': 100
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        if data.get('collection', {}).get('items'):
            item = random.choice(data['collection']['items'])
            img_url = item.get('links', [{}])[0].get('href')
            title = item.get('data', [{}])[0].get('title', 'Nature')
            desc = item.get('data', [{}])[0].get('description', '')
            
            if img_url:
                try:
                    title_ru = translator.translate(title)
                    desc_ru = translator.translate(desc[:200]) if desc else ''
                except:
                    title_ru, desc_ru = title, desc
                
                caption = f"🌎 <b>Image of the Day</b>\n\n<b>{title_ru}</b>\n\n{desc_ru}\n\n🌐 NASA"
                return {'url': img_url, 'caption': caption[:1024]}
        
        return None
    except Exception as e:
        logger.error(f"❌ NASA: {e}")
        return None

def get_github_variable(name):
    if not GH_TOKEN or not GH_REPO: return ""
    try:
        r = requests.get(f"https://api.github.com/repos/{GH_REPO}/actions/variables/{name}", 
                        headers={"Authorization": f"token {GH_TOKEN}"}, timeout=10)
        return r.json()["value"] if r.status_code == 200 else ""
    except: return ""

def set_github_variable(name, value):
    if not GH_TOKEN or not GH_REPO: return
    try:
        r = requests.patch(f"https://api.github.com/repos/{GH_REPO}/actions/variables/{name}", 
                          headers={"Authorization": f"token {GH_TOKEN}"}, 
                          json={"name": name, "value": value}, timeout=10)
        if r.status_code == 404:
            requests.post(f"https://api.github.com/repos/{GH_REPO}/actions/variables", 
                         headers={"Authorization": f"token {GH_TOKEN}"}, 
                         json={"name": name, "value": value}, timeout=10)
    except Exception as e:
        logger.error(f"❌ Save var: {e}")

def send_image(content):
    """Отправить фото в Telegram"""
    try:
        bot = Bot(token=BOT_TOKEN)
        logger.info(f"📥 Скачивание изображения: {content['url'][:50]}...")
        
        # Скачиваем изображение
        for attempt in range(3):
            r = requests.get(content['url'], timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 429:
                logger.warning(f"⚠️ 429 Too Many Requests. Ждем 5 секунд...")
                asyncio.sleep(5)
                continue
            r.raise_for_status()
            break
        
        # Сохраняем во временный файл
        ext = '.jpg'  # По умолчанию JPG
        if 'png' in content['url'].lower():
            ext = '.png'
        elif 'gif' in content['url'].lower():
            ext = '.gif'
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
            f.write(r.content)
            path = f.name
        
        logger.info("✅ Файл скачан, отправка в Telegram...")
        
        # Отправляем как фото
        with open(path, 'rb') as photo:
            asyncio.run(bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo,
                caption=content['caption'],
                parse_mode='HTML'
            ))
        
        os.remove(path)
        logger.info("✅ Фото успешно отправлено!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False

def main():
    logger.info("️ Запуск Image of the Day бота")
    
    if not all([BOT_TOKEN, CHANNEL_ID]):
        logger.error("❌ Не все переменные окружения установлены")
        return False
    
    # Выбираем случайный источник
    source = random.choice(SOURCES)
    logger.info(f"🎯 Источник: {source}")
    
    # Получаем изображение
    if source == 'unsplash_nature':
        content = get_unsplash_image('nature landscape beautiful')
    elif source == 'unsplash_animals':
        content = get_unsplash_image('animals wildlife birds')
    elif source == 'unsplash_space':
        content = get_unsplash_image('space planet earth astronomy')
    elif source == 'wikimedia':
        content = get_wikimedia_featured()
    else:
        content = get_national_park_image()
    
    # Если не получилось, пробуем другой источник
    if not content:
        logger.warning("⚠️ Не удалось получить фото, пробуем NASA...")
        content = get_national_park_image()
    
    if not content:
        logger.warning("⚠️ Не удалось получить изображение")
        return False
    
    # Отправляем в Telegram
    if send_image(content):
        # Сохраняем дату последней публикации
        today = datetime.now().strftime('%Y-%m-%d')
        set_github_variable("LAST_IMAGE_DATE", today)
        return True
    
    return False

if __name__ == '__main__':
    exit(0 if main() else 0)
