from flask import Flask, render_template, jsonify, request, redirect, session, url_for
import openai
import os
from datetime import datetime
import pyrebase
import re

# OpenAI API Key from environment
my_secret = os.environ['token']
my_secret2 = os.environ['pidginprompt']
openai.api_key = my_secret

app = Flask('app')
app.secret_key = "your_secret_key"  # Update with a real secret key

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

# Track conversation history and prompt count
conversation_history = [{"role": "system", "content": my_secret2}]

def generate_chat_response(prompt):
    messages = conversation_history
    user_message = {"role": "user", "content": prompt}
    messages.append(user_message)
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
    try:
        answer = response['choices'][0]['message']['content'].replace('\n', '<br>')
    except:
        answer = "Oops! Try again later."
    bot_message = {"role": "assistant", "content": answer}
    conversation_history.append(bot_message)
    return answer

# Check password strength utility function
def check_password_strength(password):
    return re.match(r'^(?=.*\d)(?=.*[!@#$%^&*])(?=.*[a-z])(?=.*[A-Z]).{8,}$', password) is not None

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

                # Get user's prompt count from Firebase
                prompt_count = data[session["uid"]].get("prompt_count", 0)
                session["prompt_count"] = prompt_count
            else:
                session["name"] = "User"
                session["prompt_count"] = 0
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
            session["prompt_count"] = 0  # Initialize prompt count for the new user
            data = {"name": name, "email": email, "last_logged_in": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), "prompt_count": 0}
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
    session.pop("prompt_count", None)
    return redirect(url_for('login'))

@app.route('/chatbot', methods=['POST', 'GET'])
def chatbot():
    if not session.get("is_logged_in", False):
        return redirect(url_for('login'))

    if request.method == 'POST':
        prompt = request.form['prompt']

        # Check if the user has exceeded the prompt limit
        if session['prompt_count'] >= 2:
            return jsonify({
                'answer': "NOTIFICATION!: You've hit your free message limit. <a href='/payment'>Click here to subscribe</a>"
            }), 200

        # Generate response and increment the prompt count
        response = generate_chat_response(prompt)
        session['prompt_count'] += 1

        # Update prompt count in Firebase
        db.child("users").child(session["uid"]).update({"prompt_count": session['prompt_count']})

        return jsonify({'answer': response}), 200

    return render_template('rexhtml.html')

@app.route('/payment', methods=['POST', 'GET'])
def payment():
    return render_template('payment.html')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8000)
