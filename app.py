from flask import Flask, render_template, request, jsonify, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

# ===== HTTPS ZORLA (Talisman OLMADAN) =====
@app.before_request
def before_request():
    if request.headers.get('X-Forwarded-Proto') == 'http' and os.environ.get('RAILWAY_ENVIRONMENT'):
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)
    
# Öz domeninizi təyin edin
ALLOWED_ORIGINS = [
    "https://mychatapp-production-c2ce.up.railway.app/",  # Railway domeni
    "http://localhost:5000",  # Lokal test
    "http://127.0.0.1:5000"   # Lokal test
]

# ===== SOCKETIO =====
socketio = SocketIO(app, cors_allowed_origins="ALLOWED_ORIGINS")

# Otaq şifrəsi (istəyə görə dəyişin)
ROOM_PASSWORD = "secret123"

# Yaddaş
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

@socketio.on('connect')
def handle_connect():
    print(f'✅ {request.sid} qoşuldu')
    emit('rooms_list', [{'id': r, 'name': rooms[r]['name']} for r in rooms])

@socketio.on('join')
def handle_join(data):
    room = data.get('room', 'ümumi')
    username = data.get('username', 'Anonim')
    
    if room not in rooms:
        return
    
    # Köhnə otaqdan çıx
    for r in rooms:
        if request.sid in rooms[r]['users']:
            rooms[r]['users'].discard(request.sid)
            leave_room(r)
    
    # Yeni otağa qoşul
    join_room(room)
    rooms[room]['users'].add(request.sid)
    
    # **DƏYİŞİKLİK 1:** Yalnız bu istifadəçiyə tarixçəni göndər (broadcast yox!)
    history = rooms[room]['messages'][-MAX_MESSAGES:]
    emit('history', {'messages': history, 'room': room}, to=request.sid)
    
    # **DƏYİŞİKLİK 2:** Qoşulma mesajını yalnız digər istifadəçilərə göndər
    msg = {'username': 'System', 'message': f'👋 {username} qoşuldu!', 'type': 'system'}
    rooms[room]['messages'].append(msg)
    emit('message', msg, to=room)
    emit('user_count', {'room': room, 'count': len(rooms[room]['users'])}, to=room)

# app.py - handle_message funksiyası
@socketio.on('message')
def handle_message(data):
    room = data.get('room', 'ümumi')
    username = data.get('username', 'Anonim')
    message = data.get('message', '')
    
    if room not in rooms:
        return
    
    msg = {
        'username': username,
        'message': message,
        'time': data.get('time', ''),
        'type': 'user'
    }
    rooms[room]['messages'].append(msg)
    
    if len(rooms[room]['messages']) > MAX_MESSAGES:
        rooms[room]['messages'].pop(0)
    
    # **BURADA emit iki dəfə işləyə bilər**
    emit('message', msg, to=room, include_self=False)
    
    # **Əgər bu sətir iki dəfə işləyirsə, problem burdadır**
    print(f"📤 Emit göndərildi: {msg}")

@socketio.on('disconnect')
def handle_disconnect():
    for room in rooms:
        if request.sid in rooms[room]['users']:
            rooms[room]['users'].discard(request.sid)
            emit('user_count', {'room': room, 'count': len(rooms[room]['users'])}, to=room)
    print(f'❌ {request.sid} ayrıldı')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port)