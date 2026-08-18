import os
import random
import requests
import logging
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from deep_translator import GoogleTranslator

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')

# Типы контента (чередуются)
CONTENT_TYPES = ['nature', 'space']
STATE_VAR_TYPE = "LAST_SOUND_TYPE"

translator = GoogleTranslator(source='auto', target='ru')


# ==================== ЗВУКИ ПРИРОДЫ (Xeno-canto API) ====================
def get_nature_sound():
    """Получить случайный звук птицы со всего мира через Xeno-canto API"""
    try:
        logger.info("🐦 Запрос к Xeno-canto API (звуки природы)...")
        
        # Надёжные, простые запросы, которые ВСЕГДА возвращают результат
        queries = [
            'country:"Russia"',
            'country:"Brazil"',
            'country:"Australia"',
            'country:"Kenya"',
            'country:"Indonesia"',
            'country:"Canada"',
            'country:"India"',
            'country:"Madagascar"',
            'genus:"Corvus"',      # Вороны
            'genus:"Turdus"',      # Дрозды
            'genus:"Sylvia"'       # Славки
        ]
        
        query = random.choice(queries)
        # Используем только 1 или 2 страницу, чтобы избежать пустых страниц (404)
        page = random.randint(1, 2)
        
        url = f"https://www.xeno-canto.org/api/2/recordings?query={query}&page={page}"
        headers = {'User-Agent': 'NatureSoundsBot/1.0'}
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        recordings = data.get('recordings', [])
        if not recordings:
            logger.warning("⚠️ Xeno-canto не вернул записей, пробуем другой запрос")
            return None
        
        # Выбираем случайную запись из полученных
        recording = random.choice(recordings)
        
        audio_url = recording.get('file', '')
        if not audio_url:
            return None
        
        # Делаем URL строго HTTPS
        audio_url = audio_url.replace('http://', 'https://')
        
        # Информация о записи
        species = recording.get('en', recording.get('species', 'Неизвестный вид'))
        location = recording.get('loc', 'Неизвестно')
        country = recording.get('country', '')
        recordist = recording.get('rec', 'Неизвестный автор')
        
        logger.info(f"🎵 Найдена запись: {species} ({country})")
        
        # Формируем описание на английском для перевода
        description_en = (
            f"Послушайте голос вида {species}. "
            f"Эта запись была сделана в локации: {location}, {country}, "
            f"автор записи: {recordist}. "
            f"Xeno-canto — крупнейшая в мире открытая база данных звуков птиц."
        )
        
        # Переводим
        try:
            description_ru = translator.translate(description_en)
            species_ru = translator.translate(species) if len(species) > 3 else species
        except Exception as e:
            logger.warning(f"⚠️ Ошибка перевода: {e}")
            description_ru = description_en
            species_ru = species
        
        # Формируем подпись
        caption = (
            f"🐦 <b>Звуки Земли: {species_ru}</b>\n\n"
            f"{description_ru}\n\n"
            f"📍 {location}, {country}\n"
            f"🎙️ Запись: {recordist}\n"
            f"🌐 Источник: xeno-canto.org"
        )
        
        # Обрезаем, если длинно
        if len(caption) > 1000:
            caption = caption[:1000].rsplit(' ', 1)[0] + "..."
        
        return {
            'type': 'audio',
            'url': audio_url,
            'caption': caption,
            'title': f"{species} - {country}"
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка Xeno-canto API: {e}")
        return None


# ==================== ЗВУКИ КОСМОСА (Wikimedia Commons / NASA) ====================
def get_space_sound():
    """Получить звук из космоса (вечные ссылки Wikimedia Commons с оригиналами NASA)"""
    try:
        logger.info("🚀 Выбор звука из архива космических звуков...")
        
        # ВЕЧНЫЕ ссылки на оригинальные записи NASA, размещённые на Wikimedia Commons
        nasa_sounds = [
            {
                'url': 'https://upload.wikimedia.org/wikipedia/commons/3/36/Perseverance_Mars_Microphone.ogg',
                'title_en': 'Звуки Марса от марсохода Perseverance',
                'description_en': 'Реальное аудио, записанное микрофоном марсохода Perseverance на поверхности Марса. Слышен шум марсианского ветра и работа самого аппарата.'
            },
            {
                'url': 'https://upload.wikimedia.org/wikipedia/commons/e/e0/Jupiter_radio_emissions.ogg',
                'title_en': 'Радиоизлучение Юпитера',
                'description_en': 'Мощные радиоволны, издаваемые Юпитером, преобразованные в звук. Эта запись была сделана космическим аппаратом при сближении с газовым гигантом.'
            },
            {
                'url': 'https://upload.wikimedia.org/wikipedia/commons/2/2c/Saturn_radio_emissions.ogg',
                'title_en': 'Радиоизлучение Сатурна',
                'description_en': 'Загадочные радиосигналы Сатурна, записанные зондом Cassini. Они связаны с магнитным полем планеты и её знаменитыми кольцами.'
            },
            {
                'url': 'https://upload.wikimedia.org/wikipedia/commons/8/87/Solar_wind.ogg',
                'title_en': 'Звуки солнечного ветра',
                'description_en': 'Поток заряженных частиц от Солнца. Когда эти частицы взаимодействуют с магнитным полем Земли, они создают электромагнитные колебания, преобразованные в этот звук.'
            },
            {
                'url': 'https://upload.wikimedia.org/wikipedia/commons/5/5e/Earth_VLF.ogg',
                'title_en': 'Сверхнизкочастотные звуки Земли',
                'description_en': 'Сама Земля издаёт электромагнитные звуки в сверхнизком диапазоне. Они вызваны ударами молний и взаимодействием атмосферы с солнечным ветром.'
            },
            {
                'url': 'https://upload.wikimedia.org/wikipedia/commons/9/9e/Pulsar_sound.ogg',
                'title_en': 'Звук пульсара',
                'description_en': 'Радиосигналы от быстро вращающейся нейтронной звезды (пульсара), преобразованные в слышимый диапазон. Это ритмичный "стук" космоса.'
            },
            {
                'url': 'https://upload.wikimedia.org/wikipedia/commons/0/00/Black_Hole_Perseus_Cluster.ogg',
                'title_en': 'Звуковые волны от чёрной дыры',
                'description_en': 'В 2003 году астрономы обнаружили звуковые волны от сверхмассивной чёрной дыры в скоплении Персея. Это самая низкая нота, когда-либо обнаруженная во Вселенной.'
            },
            {
                'url': 'https://upload.wikimedia.org/wikipedia/commons/9/98/Apollo_11_launch.ogg',
                'title_en': 'Запуск Аполлон-11',
                'description_en': 'Оригинальная аудиозапись старта ракеты Сатурн-5 с миссией Аполлон-11, которая впервые доставила людей на Луну в 1969 году.'
            }
        ]
        
        sound = random.choice(nasa_sounds)
        
        # Переводим
        try:
            title_ru = translator.translate(sound['title_en'])
            description_ru = translator.translate(sound['description_en'])
        except Exception as e:
            logger.warning(f"⚠️ Ошибка перевода: {e}")
            title_ru = sound['title_en']
            description_ru = sound['description_en']
        
        caption = (
            f"🚀 <b>Звуки Космоса: {title_ru}</b>\n\n"
            f"{description_ru}\n\n"
            f"🌐 Источник: NASA / Wikimedia Commons"
        )
        
        if len(caption) > 1000:
            caption = caption[:1000].rsplit(' ', 1)[0] + "..."
        
        return {
            'type': 'audio',
            'url': sound['url'],
            'caption': caption,
            'title': sound['title_en']
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения звука космоса: {e}")
        return None


# ==================== УПРАВЛЕНИЕ СОСТОЯНИЕМ ====================
def get_github_variable(var_name):
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        return ""
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables/{var_name}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()["value"]
        return ""
    except Exception as e:
        logger.warning(f"⚠️ Не удалось получить переменную {var_name}: {e}")
        return ""


def set_github_variable(var_name, value):
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        return
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables/{var_name}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    data = {"name": var_name, "value": value}
    try:
        response = requests.patch(url, headers=headers, json=data, timeout=10)
        if response.status_code == 404:
            create_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables"
            requests.post(create_url, headers=headers, json=data, timeout=10)
        logger.info(f"💾 Сохранено: {var_name} = {value}")
    except Exception as e:
        logger.error(f"❌ Не удалось сохранить {var_name}: {e}")


def get_next_content_type():
    last_type = get_github_variable(STATE_VAR_TYPE)
    try:
        last_index = CONTENT_TYPES.index(last_type)
        next_index = (last_index + 1) % len(CONTENT_TYPES)
    except (ValueError, TypeError):
        next_index = 0
    return CONTENT_TYPES[next_index]


# ==================== ОТПРАВКА В TELEGRAM ====================
def send_audio_to_telegram(content):
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        logger.info(f"📥 Отправка аудио по ссылке: {content['url'][:60]}...")
        
        # Отправляем ПРЯМУЮ ссылку на аудио. Telegram сам его скачает и обработает.
        # Это намного надёжнее и быстрее, чем скачивать файл в память скрипта.
        asyncio.run(bot.send_audio(
            chat_id=TELEGRAM_CHANNEL_ID,
            audio=content['url'],  # Прямая ссылка
            caption=content['caption'],
            parse_mode='HTML',
            title=content['title'][:255]  # Лимит Telegram на название аудио
        ))
        
        logger.info("✅ Аудио успешно отправлено в Telegram")
        return True
        
    except TelegramError as e:
        logger.error(f"❌ Ошибка Telegram: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Общая ошибка отправки: {e}")
        return False


# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
def main():
    logger.info("🚀 Запуск бота звуков (Земля и Космос)")
    
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
        logger.error("❌ Не все переменные окружения установлены")
        return False
    
    # Определяем тип контента
    content_type = get_next_content_type()
    logger.info(f"🎯 Выбран тип: {content_type.upper()}")
    
    # Получаем звук
    if content_type == 'nature':
        content = get_nature_sound()
    else:
        content = get_space_sound()
    
    if not content:
        logger.warning(f"⚠️ Не удалось получить звук ({content_type}). Пробуем альтернативный тип...")
        
        # Если не получилось, пробуем другой тип
        alt_type = 'space' if content_type == 'nature' else 'nature'
        logger.info(f"🔄 Пробуем: {alt_type.upper()}")
        
        if alt_type == 'nature':
            content = get_nature_sound()
        else:
            content = get_space_sound()
    
    if not content:
        logger.warning("⚠️ Не удалось получить звук ни из одного источника.")
        return False
    
    # Отправляем в Telegram
    success = send_audio_to_telegram(content)
    
    if success:
        set_github_variable(STATE_VAR_TYPE, content_type)
        return True
    
    return False


if __name__ == '__main__':
    success = main()
    if success:
        exit(0)
    else:
        logger.warning("⚠️ Завершаем работу. Завтра попробуем снова!")
        exit(0)
