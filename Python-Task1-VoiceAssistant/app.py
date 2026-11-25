import datetime
import json
import os
import re
import smtplib
import threading
import webbrowser
from email.message import EmailMessage

import pyttsx3
import requests
import speech_recognition as sr

# ---------- Setup ----------
engine = pyttsx3.init()
engine.setProperty("rate", 170)          # speaking speed
recognizer = sr.Recognizer()

# Set these as environment variables (never hardcode passwords!)
WEATHER_API_KEY = os.getenv("OWM_API_KEY", "")      # OpenWeatherMap free key
EMAIL_USER = os.getenv("ASSISTANT_EMAIL", "")       # use a dummy/test account
EMAIL_PASS = os.getenv("ASSISTANT_EMAIL_PASS", "")  # app password

CONFIG_FILE = "commands.json"   # custom commands: {"open youtube": "https://youtube.com"}


def speak(text):
    """Text-to-speech for ALL responses."""
    print("Assistant:", text)
    engine.say(text)
    engine.runAndWait()


def listen():
    """Capture voice from mic and return lowercase text (or None)."""
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print("Listening...")
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)
            text = recognizer.recognize_google(audio).lower()
            print("You:", text)
            return text
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            speak("Sorry, I did not understand. Please repeat.")  # graceful error
        except sr.RequestError:
            speak("Speech service is not available. Check your internet.")
    return None


# ---------- Features ----------
def tell_time_date():
    now = datetime.datetime.now()
    speak(now.strftime("It is %I:%M %p on %A, %d %B %Y"))


def web_search(query):
    speak(f"Searching the web for {query}")
    webbrowser.open("https://www.google.com/search?q=" + query.replace(" ", "+"))


def set_reminder(amount, unit):
    seconds = amount * (60 if "minute" in unit else 3600 if "hour" in unit else 1)

    def alert():
        speak("Reminder! Your time is up.")

    threading.Timer(seconds, alert).start()
    speak(f"Reminder set for {amount} {unit}")


def get_weather(city):
    if not WEATHER_API_KEY:
        speak("Weather API key is not set.")
        return
    url = "https://api.openweathermap.org/data/2.5/weather"
    try:
        r = requests.get(url, params={"q": city, "appid": WEATHER_API_KEY,
                                      "units": "metric"}, timeout=5).json()
        if r.get("cod") != 200:
            speak("I could not find that city.")
            return
        speak(f"Weather in {city}: {r['weather'][0]['description']}, "
              f"temperature {r['main']['temp']} degrees Celsius")
    except requests.RequestException:
        speak("Could not fetch weather right now.")


def send_email():
    if not (EMAIL_USER and EMAIL_PASS):
        speak("Email credentials are not set.")
        return
    speak("Who is the receiver? Please say the email address.")
    to = listen()
    if not to:
        return
    to = to.replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
    speak("What is the message?")
    body = listen()
    if not body:
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = EMAIL_USER, to, "Message from Voice Assistant"
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        speak("Email sent successfully.")
    except Exception:
        speak("Sorry, I could not send the email.")


def load_custom_commands():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


# ---------- Intent parsing (not just keyword matching) ----------
def handle(command):
    custom = load_custom_commands()
    for phrase, target in custom.items():
        if phrase in command:
            speak(f"Opening {phrase}")
            webbrowser.open(target)
            return True

    if re.search(r"\b(hello|hi|hey)\b", command):
        speak("Hello! How can I help you today?")
    elif re.search(r"\b(time|date|day)\b", command):
        tell_time_date()
    elif m := re.search(r"remind me in (\d+) (second|minute|hour)s?", command):
        set_reminder(int(m.group(1)), m.group(2))
    elif m := re.search(r"weather (?:in|of|at) (.+)", command):
        get_weather(m.group(1))
    elif "send" in command and "email" in command:
        send_email()
    elif m := re.search(r"(?:search|google|look up)(?: for)? (.+)", command):
        web_search(m.group(1))
    elif re.search(r"\b(exit|stop|bye|quit)\b", command):
        speak("Goodbye!")
        return False
    else:
        speak("Sorry, I don't know that command yet.")
    return True


def main():
    speak("Voice assistant started. Say something.")
    running = True
    while running:
        command = listen()
        if command:
            running = handle(command)


if __name__ == "__main__":
    main()