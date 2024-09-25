from flask import Flask, render_template, jsonify, request, make_response, redirect, session, url_for
import openai
import os
from datetime import datetime
import pyrebase
import re
import requests

# Secret keys
my_secret = os.environ['token']
my_secret2 = os.environ['pidginprompt']
openai.api_key = my_secret

# Initialize Flask app
app = Flask('app')
app.secret_key = "your_secret_key"

# Configuration for Firebase
config = {
     'apiKey' : os.environ['firebase_api_key'],
     'authDomain' : "funny-eng-chatbot.firebaseapp.com",
     'databaseURL' : "https://funny-eng-chatbot-default-rtdb.firebaseio.com",
     'projectId' : "funny-eng-chatbot",
     'storageBucket' : "funny-eng-chatbot.appspot.com",
     'messagingSenderId' : "649383467646",
     'appId' : "1:649383467646:web:9155941c081d23ec44162f",
     'measurementId' : "G-6WX7ERK5R8"
}

# Initialize Firebase
firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()

# Routes for login and signup
@app.route("/")
def login():
    return render_template("login.html")

@app.route("/signup")
def signup():
    return render_template("signup.html")

@app.route("/welcome")
def welcome():
    if session.get("is_logged_in", False):
        return render_template("index.html", email=session["email"], name=session["name"])
    else:
        return redirect(url_for('login'))

def check_password_strength(password):
    return re.match(r'^(?=.*\d)(?=.*[!@#$%^&*])(?=.*[a-z])(?=.*[A-Z]).{8,}$', password) is not None

# Login route
@app.route("/result", methods=["POST", "GET"])
def result():
    if request.method == "POST":
        result = request.form
        email = result["email"]
        password = result["pass"]
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            session["is_logged_in"] = True
            session["email"] = user["email"]
            session["uid"] = user["localId"]
            data = db.child("users").get().val()
            if data and session["uid"] in data:
                session["name"] = data[session["uid"]]["name"]
                db.child("users").child(session["uid"]).update({"last_logged_in": datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})
            else:
                session["name"] = "User"
            return redirect(url_for('welcome'))
        except Exception as e:
            print("Error occurred: ", e)
            return redirect(url_for('login'))
    else:
        if session.get("is_logged_in", False):
            return redirect(url_for('welcome'))
        else:
            return redirect(url_for('login'))

# Registration route
@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        result = request.form
        email = result["email"]
        password = result["pass"]
        name = result["name"]
        if not check_password_strength(password):
            print("Password does not meet strength requirements")
            return redirect(url_for('signup'))
        try:
            auth.create_user_with_email_and_password(email, password)
            user = auth.sign_in_with_email_and_password(email, password)
            auth.send_email_verification(user['idToken'])
            session["is_logged_in"] = True
            session["email"] = user["email"]
            session["uid"] = user["localId"]
            session["name"] = name
            data = {"name": name, "email": email, "prompt_count": 0, "last_logged_in": datetime.now().strftime("%m/%d/%Y, %H:%M:%S")}
            db.child("users").child(session["uid"]).set(data)
            return render_template("verify_email.html")
        except Exception as e:
            print("Error occurred during registration: ", e)
            return redirect(url_for('signup'))
    else:
        if session.get("is_logged_in", False):
            return redirect(url_for('welcome'))
        else:
            return redirect(url_for('signup'))

# Logout route
@app.route("/logout")
def logout():
    db.child("users").child(session["uid"]).update({"last_logged_out": datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})
    session["is_logged_in"] = False
    return redirect(url_for('login'))

# Paystack Subscription Check Functions
def get_subscription_by_email(email):
    url = "https://api.paystack.co/subscription"
    headers = {
        "Authorization": "Bearer sk_test_9db0fe12af0a5cd5d29b29471888d5057b813522",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        subscriptions = response.json().get("data", [])
        for subscription in subscriptions:
            if subscription["customer"]["email"] == email:
                return subscription.get("subscription_code")
    return None

def check_subscription_status(subscription_code):
    url = f"https://check-paystack-api.onrender.com/check_subscription/{subscription_code}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('message') == "Subscription is active"
    return False

# Chatbot Route with Prompt Limit
@app.route('/chatbot', methods=['POST', 'GET'])
def rex():
    if not session.get("is_logged_in", False):
        return redirect(url_for('login'))

    if request.method == 'POST':
        prompt = request.form['prompt']

        # Fetch user data from Firebase
        user_data = db.child("users").child(session["uid"]).get().val()
        if not user_data:
            return jsonify({'answer': "Error: User data not found."}), 400

        # Get the user's prompt count from Firebase, default to 0 if it doesn't exist
        prompt_count = user_data.get('prompt_count', 0)

        # Check if the user has exceeded the free prompt limit
        if prompt_count >= 2:
            # Check if the user has an active subscription
            if not check_subscription_status(get_subscription_by_email(session["email"])):
                return jsonify({'answer': "NOTIFICATION!: Sorry, you've hit your free message limit, or your subscription has expired. <a href='/payment'>Click here to subscribe</a>"}), 200

        # Generate the chat response
        res = {}
        res['answer'] = generateChatResponse(prompt)

        # Increment the prompt count and update it in Firebase
        prompt_count += 1
        db.child("users").child(session["uid"]).update({"prompt_count": prompt_count})

        # Create a response object
        response = make_response(jsonify(res), 200)
        return response

    return render_template('rexhtml.html')

# Function to generate chat response using OpenAI
conversation_history = [{"role": "system", "content": my_secret2}]

def generateChatResponse(prompt):
    messages = conversation_history
    user_message = {"role": "user", "content": prompt}
    messages.append(user_message)

    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)

    try:
        answer = response['choices'][0]['message']['content'].replace('\n', '<br>')
    except:
        answer = "Oops! Try again later"

    bot_message = {"role": "assistant", "content": answer}
    conversation_history.append(bot_message)

    return answer

# Run the Flask app
app.run(debug=True, host='0.0.0.0', port=8000)
