# Importing necessary modules
from flask import Flask, render_template, jsonify, request, make_response, redirect, session, url_for
import os
from datetime import datetime
import pyrebase

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
db = firebase.database()

# Flask app setup
app = Flask('app')
app.secret_key = "your_secret_key"

conversation_history = [{"role": "system", "content": os.environ['pidginprompt']}]

# Function to generate chat response (using your chatbot or openai)
def generateChatResponse(prompt):
    # Add the user's new question to conversation history
    user_message = {"role": "user", "content": prompt}
    conversation_history.append(user_message)

    # Dummy response for illustration (replace with actual chat logic)
    response = "This is a dummy response."

    # Store the bot's response in the conversation history
    bot_message = {"role": "assistant", "content": response}
    conversation_history.append(bot_message)

    return response

# Route for the chatbot
@app.route('/chatbot', methods=['POST', 'GET'])
def chatbot():
    # Check if user is logged in
    if not session.get("is_logged_in", False):
        return redirect(url_for('login'))

    if request.method == 'POST':
        prompt = request.form['prompt']
        email = session['email']

        # Retrieve user data from Firebase
        user_data = db.child("users").child(session['uid']).get().val()

        # Check if the user has a record of free prompts used
        if 'free_prompts_used' not in user_data:
            free_prompts_used = 0
        else:
            free_prompts_used = user_data['free_prompts_used']

        # Check if the user has used 2 free prompts
        if free_prompts_used >= 2:
            return jsonify({'answer': "You've reached your free prompt limit. Please subscribe to continue."}), 200

        # Generate chat response
        response = generateChatResponse(prompt)

        # Increment the free prompt count and update Firebase
        free_prompts_used += 1
        db.child("users").child(session['uid']).update({"free_prompts_used": free_prompts_used})

        return jsonify({'answer': response}), 200

    return render_template('rexhtml.html')

# User login (for demonstration purposes)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Simulate user login (replace with your Firebase auth)
        session['is_logged_in'] = True
        session['email'] = 'user@example.com'  # Replace with actual user email
        session['uid'] = 'some-unique-user-id'  # Replace with actual user UID

        # Initialize user data in Firebase if it doesn't exist
        user_data = db.child("users").child(session['uid']).get().val()
        if not user_data:
            db.child("users").child(session['uid']).set({
                "email": session['email'],
                "free_prompts_used": 0
            })

        return redirect(url_for('chatbot'))

    return render_template('login.html')

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
