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

# Firebase configuration
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
            session["prompt_count_db"] = 0
            data = {"name": name, "email": email, "prompt_count_db": 0, "last_logged_in": datetime.now().strftime("%m/%d/%Y, %H:%M:%S")}
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
    
email_for_paystack=""

@app.route('/payment', methods=['POST', 'GET'])
def payment():
    global email_for_paystack
    usr_uid = session['uid']
    email_for_paystack= db.child("users").child(usr_uid).child("email").get().val()
    return render_template('payment.html', email=email_for_paystack)

def get_subscription_by_email(email):
    url = "https://api.paystack.co/subscription"
    headers = {
        "Authorization": "Bearer pk_test_c4706f1b2ad704752356bc09a889ec5c4b9d93c5",
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
        if data.get('message') == "Subscription is active":
            return True
        else:
            return False
    return False

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

# Updated `/chatbot` route
@app.route('/chatbot', methods=['POST', 'GET'])
def rex():
    #usrr_uid = session['uid']
    #subscription_code_from_email = get_subscription_by_email(db.child("users").child(usrr_uid).child("email").get().val())
    email = session.get("email")
    subscription_code_from_email = get_subscription_by_email(email)

    subscription_code = subscription_code_from_email

    if not session.get("is_logged_in", False):
        return redirect(url_for('login'))

    if request.method == 'POST':
        prompt = request.form['prompt']
        user_uid = session['uid']  # Get the user's unique ID from the session

        # Retrieve the user's prompt count from Firebase
        try:
            prompt_count = db.child("users").child(user_uid).child("prompt_count_db").get().val()
            if prompt_count is None:
                prompt_count = 0  # Set to 0 if no record exists yet
        except Exception as e:
            print(f"Error fetching prompt count from Firebase: {e}")
            prompt_count = 0  # Default to 0 in case of an error

        res = {}
        # Check if the user has exceeded the daily limit
        if prompt_count >= 2 and not check_subscription_status(subscription_code):
            return jsonify({'answer': "NOTIFICATION!!!: Sorry, You've hit your free message limit, or your subscription has expired. <a href='https://decker-5ywk.onrender.com/payment'>Click here to continue with a weekly or monthly plan</a"}), 200
        if prompt_count >= 2 and check_subscription_status(subscription_code):
            res['answer'] = generateChatResponse(prompt)
            response = make_response(jsonify(res), 200)
            return response

        # Generate the chat response
        res['answer'] = generateChatResponse(prompt)

        # Increment the user's prompt count and update it in Firebase
        try:
            new_prompt_count = prompt_count + 1
            db.child("users").child(user_uid).update({"prompt_count_db": new_prompt_count})
        except Exception as e:
            print(f"Error updating prompt count in Firebase: {e}")

        response = make_response(jsonify(res), 200)
        return response

    return render_template('rexhtml.html')

app.run(debug=True, host='0.0.0.0', port=8000)
