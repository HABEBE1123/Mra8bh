# main.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gartic Room Monitor - Railway Version
يلتقط صورة كل 30 ثانية للغرفة ويرسلها على Telegram
"""

import requests
import time
import json
import os
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

# قراءة tex.txt file إذا كان موجود
def load_env():
    env_path = Path('tex.txt')
    if env_path.exists():
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()

# تحميل الإعدادات
load_env()

# ========== الإعدادات ==========
TARGET_ROOM = os.getenv('TARGET_ROOM', '49r1Q8')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))  # فحص الغرفة كل 30 ثانية
SCREENSHOT_INTERVAL = int(os.getenv('SCREENSHOT_INTERVAL', '30'))  # تصوير كل 30 ثانية

# إعدادات Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# متغيرات التتبع
room_is_active = False
last_screenshot_time = 0
check_count = 0
screenshot_count = 0

def log(message):
    """طباعة رسالة مع الوقت"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] {message}')

def take_screenshot(room_code):
    """التقاط صورة للغرفة باستخدام Playwright"""
    try:
        log('📸 جاري التقاط صورة للغرفة...')
        
        with sync_playwright() as p:
            # فتح المتصفح (headless)
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu'
                ]
            )
            
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            
            # الذهاب لصفحة الغرفة (viewer)
            url = f'https://gartic.io/{room_code}/viewer'
            log(f'🌐 فتح الصفحة: {url}')
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # انتظار تحميل الصفحة
            time.sleep(3)
            
            # التقاط screenshot
            screenshot_path = f'screenshot_{int(time.time())}.png'
            page.screenshot(path=screenshot_path, full_page=False)
            
            browser.close()
            
            log(f'✅ تم التقاط الصورة: {screenshot_path}')
            return screenshot_path
            
    except Exception as e:
        log(f'❌ خطأ في التقاط الصورة: {str(e)}')
        return None

def send_screenshot_to_telegram(screenshot_path, room_data):
    """إرسال الصورة إلى Telegram"""
    global screenshot_count
    
    try:
        log('📤 جاري إرسال الصورة إلى Telegram...')
        
        screenshot_count += 1
        
        # إعداد الرسالة
        caption = f"""🎮 *الغرفة {room_data['code']} نشطة*

👥 *اللاعبين:* {room_data['quant']}/{room_data['max']}
🕐 *الوقت:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📸 *الصورة رقم:* {screenshot_count}

🔗 [انضم للغرفة](https://gartic.io/{room_data['code']})
"""
        
        # إرسال الصورة
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        
        with open(screenshot_path, 'rb') as photo:
            files = {'photo': photo}
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, files=files, data=data, timeout=30)
        
        # حذف الصورة بعد الإرسال
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
            log('🗑️ تم حذف الصورة المؤقتة')
        
        if response.status_code == 200:
            log(f'✅ تم إرسال الصورة #{screenshot_count} بنجاح!')
            return True
        else:
            log(f'❌ خطأ في إرسال الصورة: {response.text}')
            return False
            
    except Exception as e:
        log(f'❌ خطأ في إرسال الصورة: {str(e)}')
        if screenshot_path and os.path.exists(screenshot_path):
            os.remove(screenshot_path)
        return False

def send_telegram_message(message):
    """إرسال رسالة نصية إلى Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
            
    except Exception as e:
        log(f'❌ خطأ في إرسال الرسالة: {str(e)}')
        return False

def check_room_status():
    """فحص حالة الغرفة"""
    global room_is_active, last_screenshot_time, check_count
    
    check_count += 1
    log(f'🔍 فحص رقم {check_count}')
    
    try:
        api_url = 'https://api.allorigins.win/get?url=' + \
                  requests.utils.quote('https://gartic.io/req/list?language[]=19')
        
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        rooms = json.loads(data['contents'])
        
        log(f'📊 تم العثور على {len(rooms)} غرفة نشطة')
        
        # البحث عن الغرفة المستهدفة
        target_room = None
        for room in rooms:
            if room['code'] == TARGET_ROOM:
                target_room = room
                break
        
        if target_room:
            log(f'✨ الغرفة {TARGET_ROOM} نشطة!')
            log(f'   اللاعبين: {target_room["quant"]}/{target_room["max"]}')
            
            # إذا الغرفة جديدة (أول مرة نلقاها)
            if not room_is_active:
                room_is_active = True
                send_telegram_message(f'🎉 *تم العثور على الغرفة!*\n\nبدء المراقبة المستمرة...')
                log('🚀 بدء التصوير المستمر')
            
            # تصوير كل SCREENSHOT_INTERVAL ثانية
            current_time = time.time()
            if current_time - last_screenshot_time >= SCREENSHOT_INTERVAL:
                screenshot_path = take_screenshot(target_room['code'])
                if screenshot_path:
                    send_screenshot_to_telegram(screenshot_path, target_room)
                    last_screenshot_time = current_time
            
        else:
            log(f'⚠️  الغرفة {TARGET_ROOM} غير موجودة حالياً')
            
            # إذا الغرفة كانت نشطة وتوقفت
            if room_is_active:
                room_is_active = False
                send_telegram_message(f'🛑 *الغرفة {TARGET_ROOM} أصبحت غير نشطة*\n\nتم إيقاف التصوير مؤقتاً.')
                log('⏸️ توقف التصوير - الغرفة غير نشطة')
            
    except Exception as e:
        log(f'❌ خطأ: {str(e)}')

def test_telegram_setup():
    """اختبار إعدادات Telegram"""
    log('🤖 جاري اختبار إعدادات Telegram...')
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log('⚠️  تحذير: لم يتم تعيين TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID')
        return False
    
    try:
        result = send_telegram_message('✅ *تم تشغيل مراقب Gartic بنجاح!*\n\n🔍 جاري البحث عن الغرفة...')
        
        if result:
            log('✅ إعدادات Telegram صحيحة!')
            return True
        else:
            log('❌ خطأ في إعدادات Telegram')
            return False
            
    except Exception as e:
        log(f'❌ خطأ في اختبار Telegram: {str(e)}')
        return False

def main():
    """الدالة الرئيسية"""
    log('🚀 بدء مراقبة غرف Gartic - Railway Version')
    log(f'📌 الغرفة المستهدفة: {TARGET_ROOM}')
    log(f'⏱️  فترة الفحص: {CHECK_INTERVAL} ثانية')
    log(f'📸 فترة التصوير: {SCREENSHOT_INTERVAL} ثانية')
    log('═' * 60)
    
    # اختبار Telegram
    telegram_ok = test_telegram_setup()
    if not telegram_ok:
        log('⚠️  تحذير: مشكلة في إعدادات Telegram')
        return
    
    log('✅ البرنامج يعمل الآن...')
    log('📸 سيتم التقاط صورة كل 30 ثانية عندما تكون الغرفة نشطة')
    log('')
    
    try:
        # المراقبة المستمرة
        while True:
            check_room_status()
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        log('\n👋 إيقاف البرنامج...')
        log(f'📊 إحصائيات:')
        log(f'   - عمليات الفحص: {check_count}')
        log(f'   - الصور الملتقطة: {screenshot_count}')
        
        if room_is_active:
            send_telegram_message('👋 تم إيقاف مراقب Gartic')
            
    except Exception as e:
        log(f'❌ خطأ غير متوقع: {str(e)}')
        send_telegram_message(f'❌ خطأ في البرنامج:\n```{str(e)}```')
        raise

if __name__ == '__main__':
    main()
