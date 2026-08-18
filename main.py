import os, random, requests, logging, asyncio, tempfile, time
from telegram import Bot
from deep_translator import GoogleTranslator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
GH_TOKEN = os.getenv('GITHUB_TOKEN')
GH_REPO = os.getenv('GITHUB_REPOSITORY')

TYPES = ['nature', 'space']
translator = GoogleTranslator(source='auto', target='ru')

def get_nature():
    try:
        # Используем корректные короткие коды стран (cnt)
        q = random.choice(['cnt:RU', 'cnt:BR', 'cnt:AU', 'cnt:KE', 'cnt:IN', 'genus:Corvus', 'genus:Turdus'])
        r = requests.get(f"https://www.xeno-canto.org/api/2/recordings?query={q}&page=1", headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        r.raise_for_status()
        rec = random.choice(r.json().get('recordings', []))
        url = rec.get('file', '').replace('http://', 'https://')
        if not url: return None
        sp, loc, cnt, rec_name = rec.get('en', 'Птица'), rec.get('loc', 'Неизвестно'), rec.get('country', ''), rec.get('rec', 'Неизвестно')
        desc = translator.translate(f"Голос вида {sp}. Локация: {loc}, {cnt}. Автор: {rec_name}. Источник: xeno-canto.org")
        cap = f"🐦 <b>Звуки Земли: {translator.translate(sp) if len(sp)>3 else sp}</b>\n\n{desc}\n\n📍 {loc}, {cnt}\n🎙️ {rec_name}"
        return {'type': 'audio', 'url': url, 'caption': cap[:1000], 'title': f"{sp} - {cnt}"}
    except Exception as e:
        logger.error(f"❌ Xeno-canto: {e}")
        return None

def get_space():
    try:
        sounds = [
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/3/36/Perseverance_Mars_Microphone.ogg', 't': 'Звуки Марса (Perseverance)', 'd': 'Реальное аудио с микрофона марсохода. Слышен шум марсианского ветра.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/e/e0/Jupiter_radio_emissions.ogg', 't': 'Радиоизлучение Юпитера', 'd': 'Мощные радиоволны Юпитера, преобразованные в звук космическим аппаратом.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/2/2c/Saturn_radio_emissions.ogg', 't': 'Радиоизлучение Сатурна', 'd': 'Радиосигналы Сатурна, записанные зондом Cassini.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/8/87/Solar_wind.ogg', 't': 'Звуки солнечного ветра', 'd': 'Поток заряженных частиц от Солнца, преобразованный в звук.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/5/5e/Earth_VLF.ogg', 't': 'Сверхнизкочастотные звуки Земли', 'd': 'Электромагнитные звуки Земли, вызванные молниями и солнечным ветром.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/9/9e/Pulsar_sound.ogg', 't': 'Звук пульсара', 'd': 'Радиосигналы от быстро вращающейся нейтронной звезды.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/0/00/Black_Hole_Perseus_Cluster.ogg', 't': 'Звуковые волны от чёрной дыры', 'd': 'Самая низкая нота, когда-либо обнаруженная во Вселенной.'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/9/98/Apollo_11_launch.ogg', 't': 'Запуск Аполлон-11', 'd': 'Оригинальная аудиозапись старта ракеты Сатурн-5 в 1969 году.'}
        ]
        s = random.choice(sounds)
        cap = f"🚀 <b>Звуки Космоса: {translator.translate(s['t'])}</b>\n\n{translator.translate(s['d'])}\n\n🌐 NASA / Wikimedia Commons"
        return {'type': 'audio', 'url': s['url'], 'caption': cap[:1000], 'title': s['t']}
    except Exception as e:
        logger.error(f"❌ Космос: {e}")
        return None

def get_var(name):
    if not GH_TOKEN or not GH_REPO: return ""
    try:
        r = requests.get(f"https://api.github.com/repos/{GH_REPO}/actions/variables/{name}", headers={"Authorization": f"token {GH_TOKEN}"}, timeout=10)
        return r.json()["value"] if r.status_code == 200 else ""
    except: return ""

def set_var(name, val):
    if not GH_TOKEN or not GH_REPO: return
    try:
        r = requests.patch(f"https://api.github.com/repos/{GH_REPO}/actions/variables/{name}", headers={"Authorization": f"token {GH_TOKEN}"}, json={"name": name, "value": val}, timeout=10)
        if r.status_code == 404:
            requests.post(f"https://api.github.com/repos/{GH_REPO}/actions/variables", headers={"Authorization": f"token {GH_TOKEN}"}, json={"name": name, "value": val}, timeout=10)
    except Exception as e:
        logger.error(f"❌ Save var: {e}")

def get_next_type():
    last = get_var("LAST_SOUND_TYPE")
    try: return TYPES[(TYPES.index(last) + 1) % len(TYPES)]
    except: return TYPES[0]

def send_audio(content):
    try:
        bot = Bot(token=BOT_TOKEN)
        logger.info(f"📥 Скачивание: {content['url'][:50]}...")
        
        # Умный цикл повторных попыток на случай ошибки 429 (Too Many Requests)
        for attempt in range(3):
            r = requests.get(content['url'], timeout=60, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            if r.status_code == 429:
                logger.warning(f"⚠️ 429 Too Many Requests. Ждем 5 секунд... (Попытка {attempt + 1})")
                time.sleep(5)
                continue
            r.raise_for_status()
            break
        else:
            logger.error("❌ Не удалось скачать файл после 3 попыток")
            return False
            
        ext = ".ogg" if "ogg" in content['url'] else ".mp3"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
            f.write(r.content)
            path = f.name
            
        logger.info("✅ Файл скачан, отправка в Telegram...")
        with open(path, 'rb') as audio:
            asyncio.run(bot.send_audio(chat_id=CHANNEL_ID, audio=audio, caption=content['caption'], parse_mode='HTML', title=content['title'][:255]))
        os.remove(path)
        logger.info("✅ Успешно отправлено!")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False

def main():
    if not all([BOT_TOKEN, CHANNEL_ID]):
        logger.error("❌ Нет токенов")
        return False
    ctype = get_next_type()
    logger.info(f"🎯 Тип: {ctype.upper()}")
    content = get_nature() if ctype == 'nature' else get_space()
    if not content:
        alt = 'space' if ctype == 'nature' else 'nature'
        logger.info(f"🔄 Альтернатива: {alt.upper()}")
        content = get_nature() if alt == 'nature' else get_space()
    if not content:
        logger.warning("⚠️ Не удалось получить звук")
        return False
    if send_audio(content):
        set_var("LAST_SOUND_TYPE", ctype)
        return True
    return False

if __name__ == '__main__':
    exit(0 if main() else 0)
