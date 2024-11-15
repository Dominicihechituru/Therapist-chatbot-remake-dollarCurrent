from flask import Flask, render_template, jsonify, request, make_response, redirect, session, flash, abort, url_for
from datetime import datetime, timedelta
import pyrebase
import os
import re
import requests
import replicate

my_secret = os.environ['token']
my_secret2 = os.environ['pidginprompt']
#mybestcontextprompt = "You are an empathetic AI"

#openai.api_key = my_secret

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




@app.route("/welcome")
def welcome():
    
    return render_template("front_welcome.html")


@app.route("/googlesignin", methods=['POST', 'GET'])
def googlesignin():
    if request.method == "POST":
        try:
            user_data = request.json
            if not user_data:
                print("No user data provided")
                return jsonify({"message": "No user data provided"}), 400

            # Process user data, assuming it contains 'email' and 'name'
            email = user_data.get("email")
            name = user_data.get("displayName")
            uid = user_data.get("uid")
            
            if not email or not name:
                print("Incomplete user data")
                return jsonify({"message": "Incomplete user data"}), 400

            # Set session variables
            session["is_logged_in"] = True
            session["email"] = email
            session["name"] = name
            session["uid"] = uid

            # Debugging prints to confirm session data is set
            print(f"User {email} signed in successfully")
            print(f"Session data: {session}")
            if not db.child("users").child(session["uid"]).get().val():
                data = {"name": name, "email": email, "prompt_count_db": 0, "last_logged_in": datetime.now().strftime("%m/%d/%Y, %H:%M:%S")}
                db.child("users").child(session["uid"]).set(data)

            # Redirect to welcome page
            #return redirect(url_for("welcome"))

        except Exception as e:
            print(f"Error during Google sign-in: {e}")
            return jsonify({"message": "An error occurred during sign-in"}), 500

    # For GET requests, just return a success message
    #return jsonify({"message": "Google Sign-In route"}), 200
    return redirect(url_for("home"))


@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/signup")
def signup():
    return render_template("signup.html")

@app.route("/")
def home():
    if session.get("is_logged_in", False):
        return render_template("index.html", email=session["email"], name=session["name"])
    else:
        return redirect(url_for('welcome'))

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
            return redirect(url_for('home'))
        except Exception as e:
            print("Error occurred: ", e)
            return redirect(url_for('login'))
    else:
        if session.get("is_logged_in", False):
            return redirect(url_for('home'))
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
            return redirect(url_for('home'))
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
    return redirect(url_for('welcome'))

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
        "Authorization": "Bearer sk_live_ca56f5de9a6ec2553c20792cfa92d61f8a2a815c",
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
    url = f"https://check-paystack-api-ct.onrender.com/check_subscription/{subscription_code}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get('message') == "Subscription is active":
            return True
        else:
            return False
    return False

'''
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
'''
'''
# Updated generateChatResponse function to use session-based conversation_history
def generateChatResponse(prompt):
    # Retrieve conversation history from session or initialize it if not found
    if 'conversation_history' not in session:
        session['conversation_history'] = [{"role": "system", "content": my_secret2}]
    
    conversation_history = session['conversation_history']
    user_message = {"role": "user", "content": prompt}
    conversation_history.append(user_message)
    
    # Generate response from OpenAI API
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=conversation_history)
    try:
        answer = response['choices'][0]['message']['content'].replace('\n', '<br>')
    except:
        answer = "Oops! Try again later"
    
    bot_message = {"role": "assistant", "content": answer}
    conversation_history.append(bot_message)
    
    # Save updated conversation history back to session
    session['conversation_history'] = conversation_history
    
    return answer
'''



#****begining of chatgpt imported code

# Set Replicate API token
os.environ['REPLICATE_API_TOKEN'] = my_secret


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







'''

# Initialize chat history
chat_history = []

def generateChatResponse(question):
    global chat_history  # Ensure we're using the global chat history
    context = ""
    chat_history.append("Context: " + context)

    # Add the latest question to the chat history
    chat_history.append("User: " + question)

    #prompt = chat_history

    # Combine context with chat history
    combined_context = context + "\n".join(chat_history)

    # Create the prompt for the model
    prompt = "Answer the question based on the following context:" + combined_context + "\n\nQuestion: " + question

    input_data = {
    "top_p": 0.9,
    "prompt":prompt,
    "min_tokens": 0,
    "temperature": 0.6,
    "prompt_template": "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\nYou are a helpful assistant<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
    "presence_penalty": 1.15
}

    output = replicate.run(
    "meta/meta-llama-3-70b-instruct",
    input=input_data
)


    # Add the response to the chat history
    chat_history.append("Bot: " + "".join(output))

    return "".join(output)

'''


        

#*****endof chatgpt imported code



@app.route('/presignupchatbot', methods=['POST', 'GET'])
def presignuprex():
    # Check if user is logged in
    #if not session.get("is_logged_in", False):
        #return redirect(url_for('login'))

    # Initialize prompt count from cookie
    prompt_count = int(request.cookies.get('prompt_count', 0))

    if request.method == 'POST':
        # Get user's prompt
        prompt = request.form['prompt']

        # Check prompt count
        if prompt_count >= 3:
            res = {'answer': "3 prompts completed"}
        else:
            try:
                # Generate chat response
                response = generateChatResponse(prompt)
                if response is None:
                    res = {'answer': "Error generating response"}
                else:
                    res = {'answer': response}
            except Exception as e:
                res = {'answer': f"Error: {str(e)}"}

        # Increment prompt count and set cookie
        prompt_count += 1
        response = make_response(jsonify(res), 200)
        
        # Set cookie expiration to 1 year
        expires = datetime.utcnow() + timedelta(days=365)
        response.set_cookie('prompt_count', str(prompt_count), 
                            expires=expires, 
                            path='/',
                            secure=True, 
                            samesite='Strict',
                            httponly=True)

        return response

    # Render template for GET requests
    return render_template('presignuprexhtml.html')




# Updated `/chatbot` route
@app.route('/chatbot', methods=['POST', 'GET'])
def rex():
    email = session.get("email")
    subscription_code_from_email = get_subscription_by_email(email)
    subscription_code = subscription_code_from_email

    if not session.get("is_logged_in", False):
        return redirect(url_for('welcome'))

    if request.method == 'POST':
        prompt = request.form['prompt']
        user_uid = session['uid']

        # Retrieve the user's prompt count and last prompt date from Firebase
        try:
            user_data = db.child("users").child(user_uid).get().val()
            prompt_count = user_data.get("prompt_count_db", 0)
            last_prompt_date = user_data.get("last_prompt_date")
        except Exception as e:
            print(f"Error fetching user data from Firebase: {e}")
            prompt_count = 0
            last_prompt_date = None

        # Check if it's a new day to reset the prompt count
        today = datetime.now().strftime("%Y-%m-%d")
        if last_prompt_date != today:
            prompt_count = 0
            db.child("users").child(user_uid).update({"prompt_count_db": prompt_count, "last_prompt_date": today})

        # Check if the user has exceeded the daily limit
        if prompt_count >= 1000 and not check_subscription_status(subscription_code):
            return jsonify({'answer': "NOTIFICATION!: Sorry, you've hit your daily free message limit, or your subscription has expired. <a href='https://akposai.onrender.com/payment'>Click here to continue with a weekly or monthly plan</a>, or check back tomorrow for another free trial."}), 200
        if prompt_count >= 1000 and check_subscription_status(subscription_code):
            response_text = generateChatResponse(prompt)
            new_prompt_count = prompt_count + 1
            db.child("users").child(user_uid).update({"prompt_count_db": new_prompt_count, "last_prompt_date": today})
            return jsonify({'answer': response_text}), 200

        # Generate the chat response and increment the prompt count
        response_text = generateChatResponse(prompt)
        new_prompt_count = prompt_count + 1
        db.child("users").child(user_uid).update({"prompt_count_db": new_prompt_count, "last_prompt_date": today})

        return jsonify({'answer': response_text}), 200

    return render_template('rexhtml.html')

app.run(debug=False, host='0.0.0.0', port=8000)
