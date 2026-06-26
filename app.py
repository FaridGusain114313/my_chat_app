# app.py - Tam Təmiz Kod (Paytaxtlar SİLİNDİ, İcazə Siyahısı Boş, Telegram MFA ilə)
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import time
import secrets
import requests
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='gevent',
    ping_timeout=60,
    ping_interval=25
)

# ===== TELEGRAM KONFİQURASİYASI =====
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN')

# İstifadəçi məlumatları: {username: {'chat_id': xxx, 'otp': xxx, 'expiry': xxx, 'verified': xxx}}
user_data = {}

# ===== İCAZƏ VERİLƏN İSTİFADƏÇİ ADLARI (BOŞ - SONRA DOLDURULAR) =====
ALLOWED_USERS = []  # Buraya icazə verilən istifadəçiləri əlavə edin

# ===== TELEGRAM İSTİFADƏÇİLƏRİNİN CHAT ID-LƏRİ =====
TELEGRAM_CHAT_IDS = {
    # "TelegramUsername": ChatID,
    # "FaridHuseynzada": 123456789,
}

# Otaqlar
rooms = {
    'ümumi': {
        'name': 'Ümumi Söhbət',
        'messages': [],
        'users': set()
    }
}
MAX_MESSAGES = 100

# Rate limiting
user_last_message = {}

# ===== TELEGRAM FUNKSİYALARI =====
def send_telegram_message(chat_id, text):
    """Telegram-a mesaj göndər"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram xətası: {e}")
        return False

def generate_otp():
    """6 rəqəmli OTP yarat"""
    return str(secrets.randbelow(1000000)).zfill(6)

# ===== ROUTES =====
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/rooms/create', methods=['POST'])
def create_room():
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'Otaq adı boş ola bilməz'}), 400
    
    room_id = name.lower().replace(' ', '_')
    
    if room_id in rooms:
        return jsonify({'error': 'Bu otaq artıq var'}), 400
    
    rooms[room_id] = {
        'name': name,
        'messages': [],
        'users': set()
    }
    
    return jsonify({'id': room_id, 'name': name}), 201

# ===== SOCKET.IO EVENTLƏRİ =====
@socketio.on('connect')
def handle_connect():
    print(f'✅ {request.sid} qoşuldu')
    emit('rooms_list', [{'id': r, 'name': rooms[r]['name']} for r in rooms])

@socketio.on('request_otp')
def handle_request_otp(data):
    username = data.get('username', '').strip()
    telegram_username = data.get('telegram_username', '').strip()
    
    # Username yoxla
    if ALLOWED_USERS and username not in ALLOWED_USERS:
        emit('otp_error', {'message': f'"{username}" adı icazə verilən siyahıda yoxdur!'})
        return
    
    # Telegram username yoxla
    if not telegram_username:
        emit('otp_error', {'message': 'Zəhmət olmasa Telegram istifadəçi adınızı daxil edin!'})
        return
    
    # Telegram istifadəçisinin Chat ID-sini tap
    chat_id = TELEGRAM_CHAT_IDS.get(telegram_username)
    if not chat_id:
        emit('otp_error', {'message': f'"{telegram_username}" Telegram istifadəçisi tapılmadı! Bot ilə söhbətə başlayın.'})
        return
    
    # OTP yarat
    otp = generate_otp()
    user_data[username] = {
        'chat_id': chat_id,
        'telegram_username': telegram_username,
        'otp': otp,
        'expiry': time.time() + 300,  # 5 dəqiqə
        'verified': False
    }
    
    # Telegram-a göndər
    message = f"""🔐 *Chat Təsdiqləmə Kodu*

Salam @{telegram_username}!

Təsdiqləmə kodunuz: `{otp}`

Bu kod 5 dəqiqə ərzində etibarlıdır.

🔹 Chat-a daxil olmaq üçün bu kodu tətbiqə daxil edin.
🔹 Əgər bu sorğunu siz etməmisinizsə, bu mesajı görməzdən gəlin."""
    
    if send_telegram_message(chat_id, message):
        emit('otp_sent', {'message': f'✅ OTP {telegram_username} Telegram-ına göndərildi!'})
    else:
        emit('otp_error', {'message': '❌ OTP göndərilmədi! Telegram istifadəçi adını yoxlayın.'})

@socketio.on('verify_otp')
def handle_verify_otp(data):
    username = data.get('username', '').strip()
    otp = data.get('otp', '').strip()
    
    if not username or not otp:
        emit('otp_error', {'message': 'İstifadəçi adı və OTP tələb olunur!'})
        return
    
    if username not in user_data:
        emit('otp_error', {'message': 'OTP tələb edilməyib! Əvvəlcə OTP göndərin.'})
        return
    
    user_info = user_data[username]
    
    # Vaxtı yoxla
    if time.time() > user_info['expiry']:
        emit('otp_error', {'message': 'OTP-nin vaxtı keçib! Yenidən göndərin.'})
        return
    
    # OTP-ni yoxla
    if user_info['otp'] == otp:
        user_info['verified'] = True
        emit('otp_verified', {
            'message': '✅ OTP təsdiqləndi!',
            'username': username
        })
    else:
        emit('otp_error', {'message': '❌ Yanlış OTP! Yenidən cəhd edin.'})

@socketio.on('join')
def handle_join(data):
    room = data.get('room', 'ümumi')
    username = data.get('username', 'Anonim')
    
    # İstifadəçinin OTP təsdiqləndiyini yoxla
    if username not in user_data or not user_data[username].get('verified', False):
        emit('error', {'message': 'OTP təsdiqlənməyib! Əvvəlcə OTP-ni təsdiqləyin.'})
        return
    
    if ALLOWED_USERS and username not in ALLOWED_USERS:
        emit('error', {'message': f'"{username}" icazə verilən siyahıda yoxdur!'})
        return
    
    if room not in rooms:
        emit('error', {'message': 'Otaq tapılmadı'})
        return
    
    # Köhnə otaqdan çıx
    for r in rooms:
        if request.sid in rooms[r]['users']:
            rooms[r]['users'].discard(request.sid)
            leave_room(r)
    
    # Yeni otağa qoşul
    join_room(room)
    rooms[room]['users'].add(request.sid)
    
    # Tarixçə
    history = rooms[room]['messages'][-MAX_MESSAGES:]
    emit('history', {'messages': history, 'room': room}, to=request.sid)
    
    # Qoşulma mesajı
    msg = {'username': 'System', 'message': f'👋 {username} qoşuldu!', 'type': 'system'}
    rooms[room]['messages'].append(msg)
    emit('message', msg, to=room, include_self=False)
    emit('user_count', {'room': room, 'count': len(rooms[room]['users'])}, to=room)

@socketio.on('message')
def handle_message(data):
    room = data.get('room', 'ümumi')
    username = data.get('username', 'Anonim')
    message = data.get('message', '')
    
    if room not in rooms:
        return
    
    # Rate limiting
    user_id = request.sid
    now = time.time()
    if user_id in user_last_message:
        if now - user_last_message[user_id] < 2:
            emit('error', {'message': 'Çox sürətli! 2 saniyə gözləyin.'})
            return
    user_last_message[user_id] = now
    
    msg = {
        'username': username,
        'message': message,
        'time': data.get('time', datetime.now().strftime('%H:%M')),
        'type': 'user'
    }
    rooms[room]['messages'].append(msg)
    
    if len(rooms[room]['messages']) > MAX_MESSAGES:
        rooms[room]['messages'].pop(0)
    
    emit('message', msg, to=room, include_self=False)

@socketio.on('disconnect')
def handle_disconnect():
    for room in rooms:
        if request.sid in rooms[room]['users']:
            rooms[room]['users'].discard(request.sid)
            emit('user_count', {'room': room, 'count': len(rooms[room]['users'])}, to=room)
    print(f'❌ {request.sid} ayrıldı')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)