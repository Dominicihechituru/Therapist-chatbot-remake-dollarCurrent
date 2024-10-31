from flask import Flask, render_template, jsonify, request, make_response, redirect, session, flash, abort, url_for
import openai
import os
from datetime import datetime
import pyrebase
import re
import requests
import replicate

my_secret = os.environ['token']
my_secret2 = os.environ['pidginprompt']

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
            data = {
                "name": name,
                "email": email,
                "prompt_count": 0,
                "last_prompt_date": "",
                "last_logged_in": datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            }
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

email_for_paystack = ""

@app.route('/payment', methods=['POST', 'GET'])
def payment():
    global email_for_paystack
    usr_uid = session['uid']
    email_for_paystack = db.child("users").child(usr_uid).child("email").get().val()
    return render_template('payment.html', email=email_for_paystack)

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

def reset_daily_prompt_count(user_uid):
    """Reset the user's prompt count if it's a new day."""
    user_data = db.child("users").child(user_uid).get().val()
    if user_data:
        last_date = user_data.get("last_prompt_date", "")
        today_date = datetime.now().strftime("%Y-%m-%d")

        if last_date != today_date:
            db.child("users").child(user_uid).update({
                "prompt_count": 0,
                "last_prompt_date": today_date
            })



# Updated generateChatResponse function to use session-based conversation_history
def generateChatResponse(prompt):
    # Retrieve conversation history from session or initialize it if not found
    if 'chat_history' not in session:
        session['chat_history'] = []

    chat_history = session['chat_history']
    
    # Add the latest user input to the chat history
    chat_history.append("User: " + prompt)

    # Combine context with chat history
    #context = ""  # You can add any context you'd like here
    context = my_secret2
    combined_context = context + "\n".join(chat_history)

    # Create the prompt for the model
    full_prompt = f"Answer the question based on the following context:\n{combined_context}\n\nQuestion: {prompt}"

    input_data = {
        "top_p": 0.9,
        "prompt": full_prompt,
        "min_tokens": 0,
        "temperature": 0.6,
        "prompt_template": "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\nYou are a helpful assistant<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
        "presence_penalty": 1.15
    }

    # Call the Replicate model API to get the response
    output = replicate.run("meta/meta-llama-3-70b-instruct", input=input_data)

    # Add the bot's response to the chat history
    bot_response = "".join(output)
    chat_history.append("Bot: " + bot_response)

    # Save updated conversation history back to session
    session['chat_history'] = chat_history
    
    return bot_response



@app.route('/chatbot', methods=['POST', 'GET'])
def rex():
    if not session.get("is_logged_in", False):
        return redirect(url_for('login'))

    user_uid = session['uid']
    reset_daily_prompt_count(user_uid)  # Reset prompt count if necessary

    # Retrieve the user's current prompt count and check the date
    user_data = db.child("users").child(user_uid).get().val()
    prompt_count = user_data.get("prompt_count", 0)
    subscription_code = get_subscription_by_email(session.get("email"))

    if request.method == 'POST':
        prompt = request.form['prompt']

        if prompt_count >= 3 and not check_subscription_status(subscription_code):
            return jsonify({'answer': "NOTIFICATION!!!: Sorry, You've hit your free message limit, or your subscription has expired. <a href='https://decker-5ywk.onrender.com/payment'>Click here to continue with a weekly or monthly plan</a"}), 200
        
        res = {}
        res['answer'] = generateChatResponse(prompt)

        # Increment the user's prompt count and update it in Firebase
        try:
            new_prompt_count = prompt_count + 1
            db.child("users").child(user_uid).update({"prompt_count": new_prompt_count})
        except Exception as e:
            print(f"Error updating prompt count in Firebase: {e}")

        response = make_response(jsonify(res), 200)
        return response

    return render_template('rexhtml.html')

app.run(debug=False, host='0.0.0.0', port=8000)
