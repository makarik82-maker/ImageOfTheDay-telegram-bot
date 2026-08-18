import os
import random
import requests
import logging
import asyncio
import tempfile
from telegram import Bot
from telegram.error import TelegramError
from deep_translator import GoogleTranslator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')

CONTENT_TYPES = ['nature', 'space']
STATE_VAR_TYPE = "LAST_SOUND_TYPE"
translator = GoogleTranslator(source='auto', target='ru')

def get_nature_sound():
    try:
        logger.info("🐦 Запрос к Xeno-canto API...")
        # Используем проверенные официальные запросы
        queries = [
            'country:Russia', 'country:Brazil', 'country:Australia', 
            'country:Kenya', 'country:India', 'genus:Corvus', 'genus:Turdus'
        ]
        query = random.choice(queries)
        
        url = f"https://www.xeno-canto.org/api/2/recordings?query={query}&page=1"
        headers = {'User-Agent': 'NatureSoundsBot/1.0'}
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        recordings = data.get('recordings', [])
        if not recordings:
            return None
        
        recording = random.choice(recordings)
        audio_url = recording.get('file', '').replace('http://', 'https://')
        if not audio_url:
            return None
        
        species = recording.get('en', recording.get('species', 'Неизвестный вид'))
        location = recording.get('loc', 'Неизвестно')
        country = recording.get('country', '')
        recordist = recording.get('rec', 'Неизвестный автор')
        
        desc_en = f"Послушайте голос вида {species}. Запись сделана в локации: {location}, {country}, автор: {recordist}. Xeno-canto — крупнейшая открытая база данных звуков птиц."
        
        try:
            desc_ru = translator.translate(desc_en)
            species_ru = translator.translate(species) if len(species) > 3 else species
        except:
            desc_ru, species_ru = desc_en, species
            
        caption = f"🐦 <b>Звуки Земли: {species_ru}</b>\n\n{desc_ru}\n\n📍 {location}, {country}\n🎙️ Запись: {recordist}\n🌐 Источник: xeno-canto.org"
        if len(caption) > 1000:
            caption = caption[:1000].rsplit(' ', 1)[0] + "..."
            
        return {'type': 'audio', 'url': audio_url, 'caption': caption, 'title': f"{species} - {country}"}
    except Exception as e:
        logger.error(f"❌ Ошибка Xeno-canto: {e}")
        return None

def get_space_sound():
    try:
        logger.info("🚀 Выбор звука из архива (Wikimedia Commons)...")
        sounds = [
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/3/36/Perseverance_Mars_Microphone.ogg', 'title': 'Звуки Марса от марсохода Perseverance', 'desc': 'Реальное аудио, записанное микрофоном марсохода Perseverance. Слышен шум марсианского ветра и работа аппарата.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/e/e0/Jupiter_radio_emissions.ogg', 'title': 'Радиоизлучение Юпитера', 'desc': 'Мощные радиоволны Юпитера, преобразованные в звук. Запись сделана космическим аппаратом при сближении с газовым гигантом.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/2/2c/Saturn_radio_emissions.ogg', 'title': 'Радиоизлучение Сатурна', 'desc': 'Радиосигналы Сатурна, записанные зондом Cassini. Они связаны с магнитным полем планеты и её кольцами.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/8/87/Solar_wind.ogg', 'title': 'Звуки солнечного ветра', 'desc': 'Поток заряженных частиц от Солнца. При взаимодействии с магнитным полем Земли они создают эти электромагнитные колебания.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/5/5e/Earth_VLF.ogg', 'title': 'Сверхнизкочастотные звуки Земли', 'desc': 'Земля издаёт электромагнитные звуки в сверхнизком диапазоне, вызванные молниями и взаимодействием с солнечным ветром.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/9/9e/Pulsar_sound.ogg', 'title': 'Звук пульсара', 'desc': 'Радиосигналы от быстро вращающейся нейтронной звезды, преобразованные в слышимый диапазон. Ритмичный стук космоса.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/0/00/Black_Hole_Perseus_Cluster.ogg', 'title': 'Звуковые волны от чёрной дыры', 'desc': 'Звуковые волны от сверхмассивной чёрной дыры в скоплении Персея. Самая низкая нота, когда-либо обнаруженная во Вселенной.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/9/98/Apollo_11_launch.ogg', 'title': 'Запуск Аполлон-11', 'desc': 'Оригинальная аудиозапись старта ракеты Сатурн-5, которая впервые доставила людей на Луну в 1969 году.'}
        ]
        
        sound = random.choice(sounds)
        try:
            title_ru = translator.translate(sound['title'])
            desc_ru = translator.translate(sound['desc'])
        except:
            title_ru, desc_ru = sound['title'], sound['desc']
            
        caption = f"🚀 <b>Звуки Космоса: {title_ru}</b>\n\n{desc_ru}\n\n🌐 Источник: NASA / Wikimedia Commons"
        if len(caption) > 1000:
            caption = caption[:1000].rsplit(' ', 1)[0] + "..."
            
        return {'type': 'audio', 'url': sound['url'], 'caption': caption, 'title': title_ru}
    except Exception as e:
        logger.error(f"❌ Ошибка получения звука космоса: {e}")
        return None

def get_github_variable(var_name):
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY: return ""
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables/{var_name}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()["value"] if response.status_code == 200 else ""
    except:
        return ""

def set_github_variable(var_name, value):
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY: return
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables/{var_name}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        response = requests.patch(url, headers=headers, json={"name": var_name, "value": value}, timeout=10)
        if response.status_code == 404:
            requests.post(f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables", headers=headers, json={"name": var_name, "value": value}, timeout=10)
    except Exception as e:
        logger.error(f"❌ Не удалось сохранить {var_name}: {e}")

def get_next_content_type():
    last_type = get_github_variable(STATE_VAR_TYPE)
    try:
        return CONTENT_TYPES[(CONTENT_TYPES.index(last_type) + 1) % len(CONTENT_TYPES)]
    except:
        return CONTENT_TYPES[0]

def send_audio
