from flask import Flask, render_template, jsonify, request, make_response, redirect, session, url_for
import os
from hugchat import hugchat
from hugchat.login import Login
from datetime import datetime
import requests

# Initialize the app
app = Flask(__name__)
app.secret_key = "your_secret_key"

# HugChat login
signin = os.environ['signin']
password = os.environ['password']
mybestcontextprompt = os.environ['pidginprompt']
my_secret2 = "You are a pidgin English AI"

# Hugging Face Login
sign = Login(signin, password)
cookies = sign.login()
chatbot = hugchat.ChatBot(cookies=cookies.get_dict())

# Paystack API functions
def get_subscription_by_email(email):
    url = "https://api.paystack.co/subscription"
    headers = {
        "Authorization": "Bearer sk_test_9db0fe12af0a5cd5d29b29471888d5057b813522",  # Replace with your secret key
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
    return False

# Handle chat with prompt limit
user_prompt_count = {}
conversation_history = [{"role": "system", "content": my_secret2}]

def parla(context, question, creativity):
    prompt = "Answer the question based on the following context:" + context + "\n\nQuestion: " + question
    return chatbot.chat(prompt, temperature=float(creativity))

def generateChatResponse(prompt):
    messages = conversation_history
    user_message = {"role": "user", "content": prompt}
    messages.append(user_message)
    response = parla(mybestcontextprompt, prompt, 2.0)
    try:
        answer = response
    except:
        answer = "Oops! Try again later"
    bot_message = {"role": "assistant", "content": answer}
    conversation_history.append(bot_message)
    return answer

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

        subscription_code = get_subscription_by_email(session["email"])

        # Check if user has hit the free limit and subscription status
        if prompt_count >= 2 and not check_subscription_status(subscription_code):
            return jsonify({
                'answer': "NOTIFICATION!: Sorry, you've hit your free message limit or your subscription has expired. <a href='/payment'>Click here to subscribe</a>"
            }), 200

        # Handle subscription
        if check_subscription_status(subscription_code) or prompt_count < 2:
            res['answer'] = generateChatResponse(prompt)
            user_prompt_count[session_id] = prompt_count + 1
            return make_response(jsonify(res), 200)

    return render_template('rexhtml.html')

@app.route('/payment', methods=['POST', 'GET'])
def payment():
    return render_template('payment.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
