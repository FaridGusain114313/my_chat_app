# app.py - Otaq sistemi ilə
from flask import Flask, render_template, request, session, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Otaq şifrəsi (opsiyonel)
ROOM_PASSWORD = os.environ.get('ROOM_PASSWORD', 'secret123')

# Məlumat yaddaşı
rooms = {
    'ümumi': {
        'name': 'Ümumi Söhbət',
        'messages': [],
        'users': set()
    }
}
MAX_MESSAGES = 100

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/rooms')
def get_rooms():
    """Bütün otaqların siyahısını qaytar"""
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
    data = request.get_json()
    room_name = data.get('name', '').strip()
    
    if not room_name:
        return jsonify({'error': 'Otaq adı boş ola bilməz'}), 400
    
    room_id = room_name.lower().replace(' ', '_')
    
    if room_id in rooms:
        return jsonify({'error': 'Bu adda otaq artıq mövcuddur'}), 400
    
    rooms[room_id] = {
        'name': room_name,
        'messages': [],
        'users': set()
    }
    
    return jsonify({'id': room_id, 'name': room_name}), 201

@socketio.on('connect')
def handle_connect():
    print(f'✅ İstifadəçi qoşuldu! {request.sid}')
    emit('rooms_list', [{'id': r, 'name': rooms[r]['name']} for r in rooms])

@socketio.on('join_room')
def handle_join_room(data):
    """İstifadəçi otağa qoşulur"""
    room_id = data.get('room')
    username = data.get('username', 'Anonim')
    
    if room_id not in rooms:
        emit('error', {'message': 'Otaq tapılmadı'})
        return
    
    # Əvvəlki otaqdan çıx (əgər varsa)
    for r in rooms:
        if request.sid in rooms[r]['users']:
            rooms[r]['users'].discard(request.sid)
            leave_room(r)
    
    # Yeni otağa qoşul
    join_room(room_id)
    rooms[room_id]['users'].add(request.sid)
    
    # Otağa qoşulma mesajı
    join_message = {
        'username': 'System',
        'message': f'👋 {username} otağa qoşuldu!',
        'time': 'now',
        'type': 'system'
    }
    rooms[room_id]['messages'].append(join_message)
    emit('room_joined', {'room': room_id, 'username': username}, to=room_id)
    
    # Otaqdakı istifadəçi sayını yenilə
    emit('user_count', {'room': room_id, 'count': len(rooms[room_id]['users'])}, to=room_id)
    
    # Son mesajları göndər
    history = rooms[room_id]['messages'][-MAX_MESSAGES:]
    emit('room_history', {'messages': history, 'room': room_id})

@socketio.on('leave_room')
def handle_leave_room(data):
    """İstifadəçi otaqdan çıxır"""
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
    """Mesaj göndər"""
    room_id = data.get('room', 'ümumi')
    username = data.get('username', 'Anonim')
    message = data.get('message', '')
    
    if room_id not in rooms:
        emit('error', {'message': 'Otaq tapılmadı'})
        return
    
    message_data = {
        'username': username,
        'message': message[:500],
        'time': data.get('time', 'now'),
        'type': 'user'
    }
    
    rooms[room_id]['messages'].append(message_data)
    if len(rooms[room_id]['messages']) > MAX_MESSAGES:
        rooms[room_id]['messages'].pop(0)
    
    # Yalnız həmin otaqdakılara göndər
    emit('message', message_data, to=room_id)

@socketio.on('disconnect')
def handle_disconnect():
    """İstifadəçi ayrıldıqda"""
    for room_id in rooms:
        if request.sid in rooms[room_id]['users']:
            rooms[room_id]['users'].discard(request.sid)
            emit('user_count', {'room': room_id, 'count': len(rooms[room_id]['users'])}, to=room_id)
    print(f'❌ İstifadəçi ayrıldı! {request.sid}')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)