# app.py - Tam Düzəldilmiş Versiya
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import time
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

# ===== SOCKET.IO - CORS AÇIQ =====
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='gevent',
    ping_timeout=60,
    ping_interval=25
)

# ===== İCAZƏ VERİLƏN İSTİFADƏÇİ ADLARI (Avropa Paytaxtları) =====
ALLOWED_USERS = [
    # Qərbi Avropa
    "London", "Paris", "Berlin", "Madrid", "Lissabon",
    "Roma", "Vatikan", "San Marino", "Andorra", "Monako",
    "Luksemburq", "Brüssel", "Amsterdam", "Dublin",
    "Bern", "Vyana"
]

# ===== YADDAŞ =====
rooms = {
    'ümumi': {
        'name': 'Ümumi Söhbət',
        'messages': [],
        'users': set()
    }
}
MAX_MESSAGES = 100

# Rate limiting üçün
user_last_message = {}

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

@socketio.on('join')
def handle_join(data):
    room = data.get('room', 'ümumi')
    username = data.get('username', 'Anonim')
    
    # ===== İSTİFADƏÇİ YOXLAMASI =====
    if username not in ALLOWED_USERS:
        print(f"❌ İcazəsiz giriş cəhdi: {username}")
        emit('error', {'message': f'"{username}" adı icazə verilən siyahıda yoxdur!'})
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
    
    print(f"✅ {username} otağa qoşuldu!")

@socketio.on('message')
def handle_message(data):
    room = data.get('room', 'ümumi')
    username = data.get('username', 'Anonim')
    message = data.get('message', '')
    
    if room not in rooms:
        return
    
    # ===== RATE LIMITING (2 saniyə) =====
    user_id = request.sid
    now = time.time()
    if user_id in user_last_message:
        if now - user_last_message[user_id] < 2:
            emit('error', {'message': 'Çox sürətli mesaj göndərirsiniz! 2 saniyə gözləyin.'})
            return
    user_last_message[user_id] = now
    
    # Mesajı formatla
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

# ===== SERVER =====
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)