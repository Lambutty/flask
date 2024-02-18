from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
from flask_cors import CORS
import chromadb
import os
from chromadb.config import Settings
from spots import Spots
import jwt
from functools import wraps
from dotenv import load_dotenv
import json
import csv

load_dotenv()

AUTH = os.environ.get('AUTHTOKEN')
users = json.loads(os.environ.get('USERS'))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY')

CORS(app)


chroma_client = chromadb.HttpClient(
                        host=os.environ.get('CHROMA_URL'), 
                        port=8000,
                        settings=Settings(
                        chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                        chroma_client_auth_credentials=AUTH
                            )
                        )
collection = chroma_client.get_collection('artikel')


class Server:
    def __init__(self):
        self.clients = {}
    
    def close_client_connection(self, name):
        if not name in self.clients.keys():
            raise Exception(f'Client with name {name} not found!')
        self.clients.pop(name)
    def connect_client(self, client):
        # if client.name in self.clients.keys():
        #     raise Exception(f'Client with name {client.name} is already connected')    
        self.clients[client.name] = client
        return True
       
class Client:
    def __init__(self, name, debug=False):
        self.name = name

server = Server()

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'token' in session:
            token = session['token']
            try:
                # Decode and verify token
                payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                # Add decoded payload to request context
                request.user = payload
                username = request.user['username']
                return f(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token has expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Invalid token'}), 401
        else:
            return jsonify({'error': 'Token is missing'}), 401
    return decorated_function


def generate_token(username):
    payload = {'username': username}
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    return token

@app.before_request
def check_login():
    if request.endpoint != 'login' and 'token' not in session:
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if users.get(username) == password:
            token = generate_token(username)
            client = Client(username, debug = True)
            if server.connect_client(client):
                session['token'] = token
            response = redirect(url_for('index'))
            return response
        else:
            return 'Invalid username or password', 401
    return render_template('login.html')

@app.route('/logout',methods=['GET'])
@token_required
def logout():
    session.pop('token', None)
    
    if request.user['username']:
        server.close_client_connection(request.user['username'])
    return redirect(url_for('login'))

@app.route('/')
@token_required
def index():
    data = read_csv('articles.csv')
    return render_template('index.html',data=data)

def read_csv(filename):
    data = []
    with open(filename, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            data.append(row)
    return data

@app.route('/stop-listening', methods=['POST'])
def stop_listening():
    data = request.json
    spoken = data.get('result')
    if not spoken:
        return jsonify({'text': 'Habe leider nichts verstanden'})
    results = collection.query(
                            query_texts=[spoken],
                            n_results=1,
                            #where={"metadata_field": "document1"}, # optional filter
                            #where_document={"$contains": "nuts"} # optional filter
                        )
    # Process the result as needed
    return jsonify({'text': f"Sollten in {Spots.GANG.value} " + str(results['metadatas'][0][0][Spots.GANG.value]) + f"sein"})


# if __name__ == '__main__':
#     app.run(port=5000,host='0.0.0.0',debug=True)
