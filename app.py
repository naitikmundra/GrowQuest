from flask import Flask, request, jsonify, session,render_template,redirect,make_response
import firebase_admin
from firebase_admin import credentials, firestore
from flask_session import Session
from functools import wraps
import random
app = Flask(__name__)

# Configure session to use filesystem (better security)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = True
Session(app)

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()


def login_required(f):
    @wraps(f)  # Ensures Flask recognizes the function properly
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect('/')
        return f(*args, **kwargs)
    return wrapper
def login_required_with_plant(f):
    @wraps(f)  # Ensures Flask recognizes the function properly
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect('/')
        user_ref = db.collection("userdata").document(session['user']['uid'])
        user = user_ref.get()
        if not user.exists or not user.to_dict().get("plant"):
            return redirect('/start')
        
        return f(*args, **kwargs)
    return wrapper
def get_plants_by_country(country):
    plants_ref = db.collection("plantdata")
    query = plants_ref.where("countries", "array_contains", country)  # Use positional arguments
    results = query.stream()

    plants = [doc.to_dict() for doc in results]
    choice = random.choice(plants) if plants else None  # Pick a random plant
    return choice
@app.route('/')
def index():
    if 'user' in session:
        return redirect('/home')
    
    return render_template('landing.html')

@app.route('/start',methods=['POST','GET'])
@login_required
def start():
    if request.method == 'POST':
            data = request.json
            country = data.get('country')
            plant = get_plants_by_country(country)
            user_ref_dat = db.collection("userdata").document(session['user']['uid'])
            user_ref_dat.set({'uid':session['user']['uid'], 'plant':plant, 'streak':0,'last-streak':"Nill"})
            return jsonify(plant)
    return render_template('start.html')

@app.route('/home')
@login_required_with_plant
def home():   
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    uid = data.get('uid')
    email = data.get('email')

    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    if user_doc.exists:
        # User exists, check email
        user_data = user_doc.to_dict()
        if user_data.get('email') == email:
            session['user'] = {'uid': uid, 'email': email}  # Store in session
            return jsonify({"success": True, "message": "/home"})
        else:
            return jsonify({"success": False, "message": "/login"})
    else:
        # New user, store in database
        user_ref.set({'email': email})  # UID is already the doc ID
        session['user'] = {'uid': uid, 'email': email}  # Store in session
        return jsonify({"success": True, "message": "/start"})

@app.route('/logout')
def logout():
    if 'user' in session:
        session.pop('user', None)  # Remove user session
        session.pop('plant', None)  # Remove user session

    return redirect('/')  # Redirect to home page
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
