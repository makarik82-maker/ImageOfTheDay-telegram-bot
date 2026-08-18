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
        logger.info(" Запрос к Xeno-canto API (звуки природы)...")
        
        # Разные регионы для разнообразия
        regions = [
            "country:Russia",
            "country:Brazil",
            "country:Australia",
            "country:Kenya",
            "country:Indonesia",
            "country:Canada",
            "country:India",
            "country:Madagascar",
            "genus:Corvus",      # Вороны
            "genus:Parus",       # Синицы
            "genus:Turdus",      # Дрозды
            "genus:Phylloscopus" # Пеночки
        ]
        
        query = random.choice(regions)
        page = random.randint(1, 10)
        
        url = f"https://www.xeno-canto.org/api/2/recordings?query={query}&page={page}"
        headers = {'User-Agent': 'NatureSoundsBot/1.0'}
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        recordings = data.get('recordings', [])
        if not recordings:
            logger.warning("⚠️ Xeno-canto не вернул записей")
            return None
        
        # Выбираем случайную запись
        recording = random.choice(recordings)
        
        audio_url = recording.get('file', '')
        if not audio_url:
            return None
        
        # Делаем URL HTTPS
        audio_url = audio_url.replace('http://', 'https://')
        
        # Информация о записи
        species = recording.get('en', recording.get('species', 'Неизвестный вид'))
        location = recording.get('loc', 'Неизвестно')
        country = recording.get('country', '')
        recordist = recording.get('rec', 'Неизвестно')
        
        logger.info(f" Найдена запись: {species} ({country})")
        
        # Формируем описание на английском для перевода
        description_en = (
            f"Listen to the voice of {species}. "
            f"This recording was made in {location}, {country} "
            f"by {recordist}. "
            f"Xeno-canto is the world's largest open database of bird sounds."
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
        
        # Обрезаем если длинно
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


# ==================== ЗВУКИ КОСМОСА (NASA) ====================
def get_space_sound():
    """Получить звук из космоса (NASA Sound Archive)"""
    try:
        logger.info("🚀 Выбор звука из архива NASA...")
        
        # Проверенные прямые ссылки на звуки NASA
        nasa_sounds = [
            {
                'url': 'https://www.nasa.gov/wp-content/uploads/2021/08/Perseverance_Sols_1-7_Audio.mp3',
                'title_en': 'Sounds of Mars from Perseverance Rover',
                'description_en': 'Real audio recorded by the Perseverance rover on Mars. The microphone captured the sounds of the Martian wind and the rover itself during its first week on the Red Planet.'
            },
            {
                'url': 'https://www.nasa.gov/wp-content/uploads/2021/08/Ingenuity_Helicopter_Flight_4_Audio.mp3',
                'title_en': 'Ingenuity Helicopter on Mars',
                'description_en': 'Audio from the Ingenuity helicopter during its fourth flight on Mars. This was the first time sound from a powered aircraft on another planet was recorded.'
            },
            {
                'url': 'https://www.nasa.gov/wp-content/uploads/2021/08/Juno_Jupiter_Radio.wav',
                'title_en': 'Jupiter Radio Emissions',
                'description_en': 'Jupiter emits powerful radio waves that can be converted into sound. This recording was made by the Juno spacecraft as it orbited the gas giant.'
            },
            {
                'url': 'https://www.nasa.gov/wp-content/uploads/2021/08/Saturn_Radio.wav',
                'title_en': 'Saturn Radio Emissions',
                'description_en': 'Radio emissions from Saturn captured by the Cassini spacecraft. The planet produces mysterious radio signals related to its magnetic field.'
            },
            {
                'url': 'https://www.nasa.gov/wp-content/uploads/2021/08/Sun_Solar_Wind.wav',
                'title_en': 'Sounds of the Solar Wind',
                'description_en': 'The solar wind is a stream of charged particles from the Sun. When these particles interact with Earth magnetic field, they create sounds that can be converted to audio.'
            },
            {
                'url': 'https://www.nasa.gov/wp-content/uploads/2021/08/Earth_Very_Low_Frequency.wav',
                'title_en': 'Earth Very Low Frequency Emissions',
                'description_en': 'Earth itself produces electromagnetic sounds in the very low frequency range. These are caused by lightning strikes and interactions with the solar wind.'
            },
            {
                'url': 'https://www.nasa.gov/wp-content/uploads/2021/08/Voyager_Plasma_Wave.wav',
                'title_en': 'Voyager in Interstellar Space',
                'description_en': 'Sounds recorded by the Voyager spacecraft as it travels through interstellar space. These plasma wave vibrations reveal the density of the interstellar medium.'
            },
            {
                'url': 'https://www.nasa.gov/wp-content/uploads/2021/08/Black_Hole_Sound_Waves.wav',
                'title_en': 'Sound Waves from a Black Hole',
                'description_en': 'In 2003, astronomers detected sound waves from a supermassive black hole in the Perseus Cluster. This is the deepest note ever detected in the universe.'
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
            f"🌐 Источник: NASA Sound Archive"
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
        logger.error(f"❌ Ошибка получения звука NASA: {e}")
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
        
        # Скачиваем аудиофайл для отправки
        logger.info(f"📥 Скачивание аудио: {content['url']}")
        audio_response = requests.get(content['url'], timeout=60, stream=True)
        audio_response.raise_for_status()
        
        # Telegram принимает файлы до 50 МБ
        if int(audio_response.headers.get('content-length', 0)) > 50 * 1024 * 1024:
            logger.error("❌ Файл слишком большой (>50 МБ)")
            return False
        
        # Отправляем аудио
        asyncio.run(bot.send_audio(
            chat_id=TELEGRAM_CHANNEL_ID,
            audio=audio_response.content,
            caption=content['caption'],
            parse_mode='HTML',
            title=content['title'][:255]  # Telegram лимит на title
        ))
        
        logger.info("✅ Аудио успешно отправлено в Telegram")
        return True
        
    except TelegramError as e:
        logger.error(f"❌ Ошибка Telegram: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False


# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
def main():
    logger.info(" Запуск бота звуков (Земля и Космос)")
    
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
        logger.warning("⚠️ Не удалось получить звук. Пробуем альтернативный тип...")
        
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
        logger.warning("️ Завершаем работу. Завтра попробуем снова!")
        exit(0)
