# app.py - HTTPS/WSS ilə tam işləyən versiya
from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

# HTTPS yönləndirməsi
@app.before_request
def before_request():
    if not request.is_secure and os.environ.get('RAILWAY_ENVIRONMENT'):
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

# Təhlükəsiz WebSocket
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True
)

messages = []

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('✅ İstifadəçi qoşuldu!')
    for msg in messages:
        emit('history', msg)

@socketio.on('message')
def handle_message(data):
    print(f"📩 {data}")
    messages.append(data)
    if len(messages) > 100:
        messages.pop(0)
    emit('message', data, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)