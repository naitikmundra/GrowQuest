from flask import Flask, request, jsonify, session,render_template,redirect,make_response
import firebase_admin
from firebase_admin import credentials, firestore
from flask_session import Session
from functools import wraps
import random
import requests
from datetime import datetime

app = Flask(__name__, static_folder="assets")

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory("assets", filename)

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
            user_ref_dat.set({'uid':session['user']['uid'],'photo':session['user']["photo"], 'name':session['user']['name'],'email':session['user']['email'],'country':country, 'plant':plant, 'streak':0,'last_streak':"Nill",'first_streak':0})
            return jsonify(plant)
    return render_template('start.html')

@app.route('/home')
@login_required_with_plant
def home():
    # Query the "userdata" collection, order by "streak" in descending order
    users_ref = db.collection("userdata").order_by("streak", direction=firestore.Query.DESCENDING).stream()
    people = []
    # Iterate through the results and print or process them
    for user in users_ref:
        user_data = user.to_dict()
        people.append(user_data)

    user_ref = db.collection("userdata").document(session['user']['uid'])
    user = user_ref.get().to_dict()
    
    return render_template('index.html',user=user, people=people)


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    uid = data.get('uid')
    email = data.get('email')
    name = data.get('name')
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    photo_url = data.get('photo_url')  

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
        session['user'] = {'uid': uid, 'email': email, 'name':name, 'photo':photo_url}  # Store in session
        return jsonify({"success": True, "message": "/start"})

@app.route('/snap',methods=['POST','GET'])
@login_required_with_plant
def snap():
    if request.method == 'POST':
        API_KEY = ""  # Replace with your actual API key
        PLANTNET_URL = "https://my-api.plantnet.org/v2/identify/all"

        # Open the image file you want to send
        file = request.files['image']
        # Open the image file in binary mode
            # Prepare form data
        files = {
                'images': file,
                'organs': (None, 'leaf'),  # Modify as needed (e.g., 'leaf', 'flower', etc.)
        }

            # Send POST request to Pl@ntNet API
        response = requests.post(
                f"{PLANTNET_URL}?nb-results=10&lang=en&include-related-images=false&no-reject=false&api-key={API_KEY}",
                files=files
        )

            # Check the response
        if response.status_code == 200:
                data = response.json()
                user_ref = db.collection("userdata").document(session['user']['uid'])
                user = user_ref.get().to_dict()
                if user["first_streak"] == 0:
                        user_ref.update({
                            "first_streak":datetime.today().strftime('%Y-%m-%d')
                            })
                if user["last_streak"] == "Nill":
                        user_ref.update({
                            "last_streak":datetime.today().strftime('%Y-%m-%d')
                            })
                if abs((datetime.strptime(user["last_streak"], "%Y-%m-%d") - datetime.today()).days) > 1:
                            
                            user_ref.update({
                                "streak": 0,
                            })
                if user["last_streak"] != datetime.today().strftime('%Y-%m-%d'):
                    user_ref.update({
                        "streak": firestore.Increment(1),
                        "last_streak": datetime.today().strftime('%Y-%m-%d')
                    })
                if 'results' in data and data['results']:
                    return jsonify({"success": True, "message":f"Detected Plant: {data['results'][0]['species']['commonNames']}"})
                else:
                    return jsonify({"success": True, "message":"No plant detected."})
        else:
                    user_ref = db.collection("userdata").document(session['user']['uid'])

                    user = user_ref.get().to_dict()
                    if user["first_streak"] == 0:
                        user_ref.update({
                            "first_streak":datetime.today().strftime('%Y-%m-%d')
                            })
                    if user["last_streak"] == "Nill":
                        user_ref.update({
                            "last_streak":datetime.today().strftime('%Y-%m-%d')
                            })                        
                    if abs((datetime.strptime(user["first_streak"], "%Y-%m-%d") - datetime.today()).days) < 10:
                        if abs((datetime.strptime(user["last_streak"], "%Y-%m-%d") - datetime.today()).days) > 1:
                            
                            user_ref.update({
                                "streak": 0,
                            })
                        
                        if user["last_streak"] != datetime.today().strftime('%Y-%m-%d'):
                            user_ref.update({
                                "streak": firestore.Increment(1),
                                "last_streak": datetime.today().strftime('%Y-%m-%d')
                            })
                        

                    return jsonify({"success": True, "message":"No plant detected. Streak won't be updated unless you have been growing for less than 10 days"})

    return render_template('snap.html')
@app.route('/logout')
def logout():
    if 'user' in session:
        session.pop('user', None)  # Remove user session
        session.pop('plant', None)  # Remove user session

    return redirect('/')  # Redirect to home page
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
