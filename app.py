# app.py
from flask import Flask, render_template
from flask_socketio import SocketIO, send, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey!'

# Railway deploy üçün port tənzimləməsi
socketio = SocketIO(app, cors_allowed_origins="*")

# Yaddaşda mesajları saxlayaq (sadəlik üçün)
messages = []
MAX_MESSAGES = 100

@app.route('/')
def index():
    """Əsas chat səhifəsi"""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Yeni istifadəçi qoşulduqda"""
    print(f"✅ Yeni istifadəçi qoşuldu!")
    # Keçmiş mesajları yeni istifadəçiyə göndər
    if messages:
        for msg in messages:
            emit('history', msg)

@socketio.on('message')
def handle_message(data):
    """Yeni mesaj gəldikdə"""
    # Məlumatları yadda saxla
    message_data = {
        'username': data.get('username', 'Anonim'),
        'message': data.get('message', ''),
        'time': data.get('time', '')
    }
    
    # Son 100 mesajı saxla
    messages.append(message_data)
    if len(messages) > MAX_MESSAGES:
        messages.pop(0)
    
    # Bütün istifadəçilərə mesajı yayımla
    emit('message', message_data, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    """İstifadəçi ayrıldıqda"""
    print(f"❌ İstifadəçi ayrıldı!")

if __name__ == '__main__':
    # Railway üçün port tənzimləməsi
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)