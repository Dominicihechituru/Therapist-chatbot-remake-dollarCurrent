from flask import Flask, render_template, jsonify, request, make_response, redirect, session, flash, abort, url_for
import openai
import os
from datetime import datetime
import pyrebase
import re
import requests

my_secret = os.environ['token']
my_secret2 = os.environ['pidginprompt']

openai.api_key = my_secret

app = Flask('app')
app.secret_key = "your_secret_key"

# Configuration for Firebase
config = {
    'apiKey': os.environ['firebase_api_key'],
    'authDomain': "funny-eng-chatbot.firebaseapp.com",
    'databaseURL': "https://funny-eng-chatbot-default-rtdb.firebaseio.com",
    'projectId': "funny-eng-chatbot",
    'storageBucket': "funny-eng-chatbot.appspot.com",
    'messagingSenderId': "649383467646",
    'appId': "1:649383467646:web:9155941c081d23ec44162f",
    'measurementId': "G-6WX7ERK5R8"
}

# Initialize Firebase
firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()

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

@app.route("/first-login", methods=["POST", "GET"])
def first_login():
    return render_template("first_login.html")

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
                db.child("users").child(session["uid"]).update(
                    {"last_logged_in": datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})
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
            data = {"name": name, "email": email, "last_logged_in": datetime.now().strftime("%m/%d/%Y, %H:%M:%S")}
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

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        email = request.form["email"]
        try:
            auth.send_password_reset_email(email)
            return render_template("reset_password_done.html")
        except Exception as e:
            print("Error occurred: ", e)
            return render_template("reset_password.html", error="An error occurred. Please try again.")
    else:
        return render_template("reset_password.html")

@app.route("/logout")
def logout():
    db.child("users").child(session["uid"]).update({"last_logged_out": datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})
    session["is_logged_in"] = False
    return redirect(url_for('login'))

@app.route('/landing')
def hello_world():
    return render_template('index.html')

@app.route('/privacypolicy')
def privacypolicy():
    return render_template('privacypolicy.html')

@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')

@app.route('/contactus')
def contactus():
    return render_template('contactus.html')

@app.route('/payment', methods=['POST', 'GET'])
def payment():
    return render_template('payment.html')

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

user_prompt_count = {}

@app.route('/chatbot', methods=['POST', 'GET'])
def rex():
    if not session.get("is_logged_in", False):
        return redirect(url_for('login'))

    if request.method == 'POST':
        prompt = request.form['prompt']

        if 'session_id' not in session:
            session_id = os.urandom(16).hex()
            session['session_id'] = session_id
            user_prompt_count[session_id] = 1
        else:
            session_id = session['session_id']

        prompt_count = user_prompt_count.get(session_id, 0)
        res = {}

        if prompt_count >= 2:
            return jsonify({'answer': "NOTIFICATION!: You've hit your free message limit. <a href='/payment'>Click here to subscribe</a>"}), 200

        res['answer'] = generateChatResponse(prompt)
        user_prompt_count[session_id] = prompt_count + 1
        response = make_response(jsonify(res), 200)
        return response

    return render_template('rexhtml.html')

app.run(debug=True, host='0.0.0.0', port=8000)
