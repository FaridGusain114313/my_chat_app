# app.py - Tam işləyən chat tətbiqi
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import secrets
import re

# ==================== KONFİQURASİYA ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Socket.io tənzimləməsi
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e8,
    allow_upgrades=True,
    http_compression=True
)

# Otaq şifrəsi (environment dəyişənindən)
ROOM_PASSWORD = os.environ.get('ROOM_PASSWORD', 'secret123')

# ==================== MƏLUMATLAR ====================
rooms = {
    'ümumi': {
        'name': 'Ümumi Söhbət',
        'messages': [],
        'users': set()
    }
}
MAX_MESSAGES = 100

# ==================== ROUTES ====================
@app.route('/')
def index():
    """Əsas səhifə"""
    return render_template('index.html')

@app.route('/api/rooms')
def get_rooms():
    """Bütün otaqların siyahısı"""
    room_list = []
    for room_id, room_data in rooms.items():
        room_list.append({
            'id': room_id,
            'name': room_data['name'],
            'users': len(room_data['users'])
        })
    return jsonify(room_list)

@app.route('/api/rooms/create', methods=['POST'])
def create_room():
    """Yeni otaq yarat"""
    try:
        # JSON formatını yoxla
        if not request.is_json:
            return jsonify({'error': 'JSON formatı tələb olunur'}), 400
        
        data = request.get_json()
        room_name = data.get('name', '').strip()
        
        # Otaq adını yoxla
        if not room_name:
            return jsonify({'error': 'Otaq adı boş ola bilməz'}), 400
        
        # Yalnız icazə verilən simvollar
        if not re.match(r'^[a-zA-Z0-9\s_\-]+$', room_name):
            return jsonify({'error': 'Otaq adında yalnız hərflər, rəqəmlər və _ - istifadə edin'}), 400
        
        room_id = room_name.lower().replace(' ', '_')
        
        # Otaq mövcuddursa
        if room_id in rooms:
            return jsonify({'id': room_id, 'name': rooms[room_id]['name']}), 200
        
        # Yeni otaq yarat
        rooms[room_id] = {
            'name': room_name,
            'messages': [],
            'users': set()
        }
        
        print(f"✅ Yeni otaq yaradıldı: {room_id} - {room_name}")
        return jsonify({'id': room_id, 'name': room_name}), 201
        
    except Exception as e:
        print(f"❌ Otaq yaratma xətası: {e}")
        return jsonify({'error': f'Server xətası: {str(e)}'}), 500

# ==================== SOCKET.IO EVENTLƏRİ ====================
@socketio.on('connect')
def handle_connect():
    """İstifadəçi qoşulduqda"""
    print(f'✅ İstifadəçi qoşuldu! {request.sid}')
    emit('rooms_list', [{'id': r, 'name': rooms[r]['name']} for r in rooms])

@socketio.on('join_room')
def handle_join_room(data):
    """İstifadəçi otağa qoşulduqda"""
    room_id = data.get('room', 'ümumi')
    username = data.get('username', 'Anonim')
    
    # Otaq mövcud deyilsə
    if room_id not in rooms:
        emit('error', {'message': 'Otaq tapılmadı'})
        return
    
    # Əvvəlki otaqdan çıx
    for r in rooms:
        if request.sid in rooms[r]['users']:
            rooms[r]['users'].discard(request.sid)
            leave_room(r)
    
    # Yeni otağa qoşul
    join_room(room_id)
    rooms[room_id]['users'].add(request.sid)
    
    # Sistem mesajı
    join_message = {
        'username': 'System',
        'message': f'👋 {username} otağa qoşuldu!',
        'time': 'now',
        'type': 'system'
    }
    rooms[room_id]['messages'].append(join_message)
    
    # Yalnız digər istifadəçilərə bildir
    emit('room_joined', {'room': room_id, 'username': username}, to=room_id)
    emit('user_count', {'room': room_id, 'count': len(rooms[room_id]['users'])}, to=room_id)
    
    # Yeni istifadəçiyə tarixçəni göndər
    history = rooms[room_id]['messages'][-MAX_MESSAGES:]
    emit('room_history', {'messages': history, 'room': room_id})

@socketio.on('leave_room')
def handle_leave_room(data):
    """İstifadəçi otaqdan çıxdıqda"""
    room_id = data.get('room')
    username = data.get('username', 'Anonim')
    
    if room_id in rooms and request.sid in rooms[room_id]['users']:
        rooms[room_id]['users'].discard(request.sid)
        leave_room(room_id)
        
        leave_message = {
            'username': 'System',
            'message': f'👋 {username} otaqdan ayrıldı!',
            'time': 'now',
            'type': 'system'
        }
        rooms[room_id]['messages'].append(leave_message)
        emit('room_left', {'room': room_id, 'username': username}, to=room_id)
        emit('user_count', {'room': room_id, 'count': len(rooms[room_id]['users'])}, to=room_id)

@socketio.on('message')
def handle_message(data):
    """Yeni mesaj gəldikdə"""
    room_id = data.get('room', 'ümumi')
    username = data.get('username', 'Anonim')
    message = data.get('message', '')
    
    # Otaq mövcud deyilsə
    if room_id not in rooms:
        emit('error', {'message': 'Otaq tapılmadı'})
        return
    
    # Mesajı formatla
    message_data = {
        'username': username,
        'message': message[:500],
        'time': data.get('time', 'now'),
        'type': 'user'
    }
    
    # Yadda saxla
    rooms[room_id]['messages'].append(message_data)
    if len(rooms[room_id]['messages']) > MAX_MESSAGES:
        rooms[room_id]['messages'].pop(0)
    
    # Otaqdakı hər kəsə göndər
    emit('message', message_data, to=room_id)

@socketio.on('disconnect')
def handle_disconnect():
    """İstifadəçi ayrıldıqda"""
    for room_id in rooms:
        if request.sid in rooms[room_id]['users']:
            rooms[room_id]['users'].discard(request.sid)
            emit('user_count', {'room': room_id, 'count': len(rooms[room_id]['users'])}, to=room_id)
    print(f'❌ İstifadəçi ayrıldı! {request.sid}')

# ==================== SERVERİ BAŞLAT ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True,
        use_reloader=False
    )