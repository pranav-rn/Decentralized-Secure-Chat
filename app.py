import eventlet
eventlet.monkey_patch()

import logging
import os
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import rsa
import base64

print("Hello World")
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
# Increased ping timeout and ping interval to prevent disconnections during file transfers
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*", 
                   ping_timeout=60, ping_interval=25, max_http_buffer_size=10e6)

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

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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

        # Log message receipt but don't decode to save processing
        logging.info(f"Message from {user}")

        # Emit the message to all connected clients
        emit('message', {'user': user, 'data': encrypted_data}, broadcast=True)
    except KeyError:
        logging.error("Invalid message format received")
    except Exception as ex:
        logging.error(f"Error handling message: {ex}")

@socketio.on('file_transfer_start')
def handle_file_transfer_start(data):
    try:
        user = data['user']
        filename = data['filename']
        file_size = data['file_size']
        file_type = data.get('file_type', 'application/octet-stream')
        file_hash = data.get('file_hash', '')
        
        logging.info(f"File transfer started from {user}: {filename} ({file_size} bytes)")
        
        # Notify all clients about the incoming file
        emit('file_transfer_start', {
            'user': user,
            'filename': filename,
            'file_size': file_size,
            'file_type': file_type,
            'file_hash': file_hash
        }, broadcast=True)
    except Exception as ex:
        logging.error(f"Error handling file transfer start: {ex}")

@socketio.on('file_chunk')
def handle_file_chunk(data):
    try:
        user = data['user']
        filename = data['filename']
        chunk_id = data['chunk_id']
        total_chunks = data['total_chunks']
        encrypted_chunk = data['chunk']
        
        # Forward the chunk to all other clients without logging the content
        emit('file_chunk', {
            'user': user,
            'filename': filename,
            'chunk_id': chunk_id,
            'total_chunks': total_chunks,
            'chunk': encrypted_chunk
        }, broadcast=True, include_self=False)
        
        # Only log sequence info, not content
        if chunk_id % 10 == 0 or chunk_id == total_chunks - 1:
            logging.info(f"File chunk {chunk_id+1}/{total_chunks} for {filename} from {user} forwarded")
        
        return True  # Acknowledge receipt to client
    except Exception as ex:
        logging.error(f"Error handling file chunk: {ex}")
        return False

@socketio.on('file_transfer_complete')
def handle_file_transfer_complete(data):
    try:
        user = data['user']
        filename = data['filename']
        file_hash = data.get('file_hash', '')
        
        logging.info(f"File transfer completed from {user}: {filename}")
        
        emit('file_transfer_complete', {
            'user': user,
            'filename': filename,
            'file_hash': file_hash
        }, broadcast=True)
    except Exception as ex:
        logging.error(f"Error handling file transfer complete: {ex}")

@socketio.on('disconnect')
def handle_disconnect():
    for user, sid in list(connected_clients.items()):  # Use list to avoid modification during iteration
        if sid == request.sid:
            del connected_clients[user]
            logging.info(f"Client {user} disconnected")
            break

if __name__ == '__main__':
    HOST = '0.0.0.0'
    PORT = 5000
    # Increased websocket max size
    socketio.run(app, host=HOST, port=PORT, debug=False)