import eventlet
eventlet.monkey_patch()

import logging
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import rsa
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Generate public + private keypair
publicKey, privateKey = rsa.newkeys(2048)

# Store connected clients and their public keys
connected_clients = {}

# Generate a symmetric key (base64 encoded for ease of transport)
symmetric_key = base64.b64encode(rsa.randnum.read_random_bits(256)).decode('utf-8')

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    logging.info(f"Client connected: {request.sid}")
    emit('symmetric_key', {'symmetric_key': symmetric_key})

@socketio.on('connect_user')
def handle_connect_user(data):
    try:
        user = data['user']
        logging.info(f"Client {user} connected")
        connected_clients[user] = request.sid
    except Exception as ex:
        logging.error(f"Error handling connect: {ex}")

@socketio.on('message')
def handle_message(data):
    try:
        user = data['user']
        encrypted_data = data['data']

        # Decode base64 encoded data
        encrypted_data_bytes = base64.b64decode(encrypted_data)

        logging.info(f"Message from {user}: {encrypted_data_bytes}")

        # Emit the message to all connected clients
        emit('message', {'user': user, 'data': encrypted_data}, broadcast=True)
    except KeyError:
        logging.error("Invalid message format received")
    except Exception as ex:
        logging.error(f"Error handling message: {ex}")

@socketio.on('disconnect')
def handle_disconnect():
    for user, sid in connected_clients.items():
        if sid == request.sid:
            del connected_clients[user]
            logging.info(f"Client {user} disconnected")
            break

if __name__ == '__main__':
    HOST = '0.0.0.0'
    PORT = 5000
    socketio.run(app, host=HOST, port=PORT, debug=False)
