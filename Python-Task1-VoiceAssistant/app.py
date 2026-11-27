import datetime
import difflib
import json
import math
import operator
import os
import random
import re
import urllib.parse
import urllib.request
import webbrowser
from collections import Counter

import pyttsx3
import speech_recognition as sr

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "commands.json")

DEFAULT_CONFIG = {
    "assistant_name": "Nova",
    "debug": True,
    "knowledge_base": {
        "capital of india": "The capital of India is New Delhi.",
        "capital of france": "The capital of France is Paris.",
        "speed of light": "The speed of light is about 299,792 kilometres per second.",
    },
    "custom_commands": {
        "what is your name": {"type": "say", "value": "My name is {name}, your voice assistant."},
        "who made you": {"type": "say", "value": "I was built in Python as an internship project."},
        "open my github": {"type": "url", "value": "https://github.com"},
    },
}


def save_config(cfg=None):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg or CONFIG, f, indent=2, ensure_ascii=False)


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, json.JSONDecodeError) as e:
            print(f"Could not read commands.json ({e}). Using defaults.")
    else:
        save_config(cfg)
    return cfg


CONFIG = load_config()
NAME = CONFIG["assistant_name"]


def speak(text):
    print(f"Assistant: {text}")
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 170)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"(Voice output error: {e})")


recognizer = sr.Recognizer()
recognizer.pause_threshold = 0.9


def listen(timeout=6):
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=0.4)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=12)
        except sr.WaitTimeoutError:
            return None
    try:
        text = recognizer.recognize_google(audio).lower().strip()
        print(f"You: {text}")
        return text
    except sr.UnknownValueError:
        speak("Sorry, I did not catch that. Could you please repeat?")
    except sr.RequestError:
        speak("I can't reach the speech service. Please check your internet connection.")
    return None


def ask(question, tries=3):
    speak(question)
    for _ in range(tries):
        answer = listen()
        if answer:
            return answer
    return None


STOPWORDS = {
    "the", "a", "an", "is", "are", "am", "was", "it", "me", "my", "you", "your",
    "to", "of", "in", "on", "at", "for", "please", "can", "could", "would", "do",
    "does", "i", "like", "now", "there", "this", "that", "and", "with", "some",
    "just", "today", "tomorrow", "current", "right", "exact", "up",
}

SYNONYMS = {
    "hi": "hello", "hey": "hello", "howdy": "hello", "greetings": "hello",
    "hour": "time", "clock": "time", "oclock": "time",
    "day": "date", "calendar": "date",
    "google": "search", "lookup": "search", "browse": "search", "find": "search",
    "launch": "open", "start": "open", "visit": "open",
    "laugh": "joke", "funny": "joke", "humor": "joke",
    "goodbye": "bye", "quit": "bye", "exit": "bye", "stop": "bye", "terminate": "bye",
    "teach": "add", "learn": "add", "create": "add",
}

INTENT_EXAMPLES = {
    "greeting": ["hello", "hi there", "hey assistant", "good morning", "good evening", "good afternoon"],
    "time": ["what time is it", "tell me the current time", "what is the time now",
             "do you have the time", "what hour is it"],
    "date": ["what is the date today", "what day is it", "tell me the date", "which day is today"],
    "search": ["search for python tutorials", "google machine learning", "look up best pizza places",
               "find information about climate change", "browse for cheap flights"],
    "open_site": ["open youtube", "launch google", "go to github", "visit the wikipedia website"],
    "joke": ["tell me a joke", "make me laugh", "say something funny", "do you know any jokes"],
    "add_command": ["add a custom command", "teach you a new command", "create a new command",
                    "learn a new phrase", "i want to add a command"],
    "help": ["help", "list your features", "show your abilities"],
    "bye": ["goodbye", "exit", "quit the assistant", "stop listening", "see you later", "bye bye"],
    "knowledge": ["who is albert einstein", "what is photosynthesis", "tell me about the moon",
                  "explain how gravity works", "define democracy", "who invented the telephone",
                  "where is mount everest", "when did world war two end", "why is the sky blue"],
}

BOOSTS = [
    ("help", re.compile(r"\bwhat (?:can|could) you do\b|\bwhat do you do\b|\bhelp\b|\byour (?:features|abilities|skills)\b"), 1.0),
    ("greeting", re.compile(r"\bhow are you\b|\bhow is it going\b|\bhow do you do\b"), 1.0),
]

QUESTION_RE = re.compile(r"^(who|what|where|when|why|how|which)\b")
THRESHOLD = 0.35

CALC_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)"
    r"(?:\s*(\+|\*|/|x|×|÷)\s*|\s+(-|plus|minus|times|multiplied by|divided by)\s+)"
    r"(-?\d+(?:\.\d+)?)"
)

OPS = {
    "+": operator.add, "plus": operator.add,
    "-": operator.sub, "minus": operator.sub,
    "*": operator.mul, "x": operator.mul, "×": operator.mul,
    "times": operator.mul, "multiplied by": operator.mul,
    "/": operator.truediv, "÷": operator.truediv, "divided by": operator.truediv,
}


def stem(word):
    for suffix in ("ing", "ed", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def normalize(text):
    text = text.lower().replace("'s", "").replace("'", "")
    tokens = []
    for w in re.findall(r"[a-z0-9]+", text):
        if w in STOPWORDS:
            continue
        tokens.append(SYNONYMS.get(w) or SYNONYMS.get(stem(w)) or stem(w))
    return tokens


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(count * b.get(word, 0) for word, count in a.items())
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0


EXAMPLE_VECS = {
    intent: [Counter(normalize(example)) for example in examples]
    for intent, examples in INTENT_EXAMPLES.items()
}


def parse_intent(text):
    if CALC_RE.search(text):
        return "calculate", 1.0
    tokens = Counter(normalize(text))
    scores = {
        intent: max(cosine(tokens, v) for v in vectors)
        for intent, vectors in EXAMPLE_VECS.items()
    }
    for intent, pattern, boost in BOOSTS:
        if pattern.search(text):
            scores[intent] += boost
    if QUESTION_RE.match(text):
        scores["knowledge"] += 0.15
    best = max(scores, key=scores.get)
    if scores[best] < THRESHOLD:
        return "knowledge", scores[best]
    return best, scores[best]


GREETINGS = [
    "Hello! I'm {name}. How can I help you?",
    "Hi there! What can I do for you?",
    "Hey! {name} here, ready to help.",
]

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "Why did the developer go broke? Because he used up all his cache.",
    "I would tell you a UDP joke, but you might not get it.",
]

SITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com",
    "wikipedia": "https://www.wikipedia.org", "github": "https://github.com",
    "gmail": "https://mail.google.com", "stackoverflow": "https://stackoverflow.com",
    "linkedin": "https://www.linkedin.com", "twitter": "https://twitter.com",
}

BROWSER_RE = re.compile(r"\s+(?:in|on|using|with|via)\s+(?:the\s+)?(?:google\s+)?(chrome|browser)\b.*$")

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

SEARCH_RE = re.compile(
    r"\b(?:search(?:\s+the\s+web)?(?:\s+for|\s+about|\s+on)?|google|look\s*up|"
    r"find(?:\s+me)?(?:\s+information|\s+info|\s+results)?(?:\s+on|\s+about|\s+for)?|"
    r"browse(?:\s+for)?)\s+(.+)$"
)

OPEN_RE = re.compile(r"\b(?:open|launch|start|go to|visit)\s+(?:the\s+)?(.+?)(?:\s+(?:website|site|page|app))?$")

HEADERS = {"User-Agent": "VoiceAssistantStudentProject/1.0 (Python urllib)", "Accept": "application/json"}

TOPIC_PREFIX = re.compile(
    r"^(?:please|can you|could you|would you|do you know|i want to know|i would like to know|"
    r"tell me|explain|describe|define|what is|what's|what are|what was|who is|who was|who's|"
    r"who are|about|the|a|an)\b\s*"
)


def clean(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def split_browser(text):
    m = BROWSER_RE.search(text)
    return (BROWSER_RE.sub("", text).strip(), m.group(1)) if m else (text.strip(), None)


def open_url(url, browser=None):
    if browser == "chrome":
        for path in CHROME_PATHS:
            if os.path.exists(path):
                webbrowser.register("chrome-custom", None, webbrowser.BackgroundBrowser(path))
                webbrowser.get("chrome-custom").open(url)
                return
        speak("I couldn't find Chrome, so I'll use your default browser.")
    webbrowser.open(url)


def h_greeting(text):
    if re.search(r"\bhow are you\b", text):
        speak("I'm doing great, thanks for asking! How can I help you?")
    else:
        speak(random.choice(GREETINGS).format(name=NAME))
    return True


def h_time(text):
    speak("The time is " + datetime.datetime.now().strftime("%I:%M %p").lstrip("0"))
    return True


def h_date(text):
    now = datetime.datetime.now()
    speak(f"Today is {now:%A, %B} {now.day}, {now.year}")
    return True


def h_joke(text):
    speak(random.choice(JOKES))
    return True


def h_help(text):
    speak("I can tell the time and date, do simple maths, search the web, open websites, "
          "answer questions from Wikipedia, and learn custom commands.")
    return True


def h_bye(text):
    speak("Goodbye! Have a great day.")
    return False


def h_calculate(text):
    m = CALC_RE.search(text)
    a, b = float(m.group(1)), float(m.group(4))
    op = m.group(2) or m.group(3)
    if op in ("/", "÷", "divided by") and b == 0:
        speak("You can't divide by zero.")
        return True
    result = OPS[op](a, b)
    shown = int(result) if result == int(result) else round(result, 4)
    speak(f"The answer is {shown}")
    return True


def h_search(text):
    m = SEARCH_RE.search(text)
    query, browser = split_browser(m.group(1)) if m else (None, None)
    if query:
        query = re.sub(r"\s+(?:on|in)\s+(?:google|the web|the internet|youtube)$|\s+online$|\s+please$", "", query).strip()
    if not query:
        query = ask("What would you like me to search for?")
    if not query:
        return True
    speak(f"Searching the web for {query}")
    open_url("https://www.google.com/search?q=" + urllib.parse.quote_plus(query), browser)
    return True


def h_open_site(text):
    m = OPEN_RE.search(text)
    name, browser = split_browser(m.group(1)) if m else (None, None)
    name = re.sub(r"\s+(?:website|site|page|app)$", "", name or "").strip()
    if not name:
        name = ask("Which website should I open?")
    if not name:
        return True
    url = SITES.get(name.replace(" ", ""))
    if url:
        speak(f"Opening {name}")
    else:
        speak(f"I don't know that site, so I'll search for {name}")
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(name)
    open_url(url, browser)
    return True


def extract_topic(text):
    topic = text.strip(" ?.!")
    while True:
        new = TOPIC_PREFIX.sub("", topic).strip()
        if new == topic:
            return topic
        topic = new


def wiki_answer(topic, sentences=2):
    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": topic, "gsrlimit": 3, "prop": "extracts",
        "exintro": 1, "explaintext": 1, "exsentences": sentences, "redirects": 1,
    })
    req = urllib.request.Request("https://en.wikipedia.org/w/api.php?" + params, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Wikipedia error: {e}")
        return None
    pages = data.get("query", {}).get("pages", {})
    for page in sorted(pages.values(), key=lambda p: p.get("index", 999)):
        extract = page.get("extract", "").strip()
        if extract:
            return re.sub(r"\s*\([^)]*\)", "", extract)
    return None


def h_knowledge(text):
    kb = {clean(k): v for k, v in CONFIG["knowledge_base"].items()}
    spoken_text = clean(text)
    for key, answer in kb.items():
        if key and key in spoken_text:
            speak(answer)
            return True
    topic = extract_topic(text)
    if not topic:
        speak("What would you like to know about?")
        return True
    close = difflib.get_close_matches(clean(topic), list(kb), n=1, cutoff=0.85)
    if close:
        speak(kb[close[0]])
        return True
    speak(f"Let me look that up: {topic}")
    summary = wiki_answer(topic)
    speak(summary if summary else "Sorry, I couldn't find an answer to that.")
    return True


def match_custom(text):
    commands = {clean(k): v for k, v in CONFIG["custom_commands"].items()}
    t = clean(text)
    if t in commands:
        return commands[t]
    close = difflib.get_close_matches(t, list(commands), n=1, cutoff=0.85)
    return commands[close[0]] if close else None


def run_custom(cmd):
    kind, value = cmd.get("type"), cmd.get("value", "")
    if kind == "say":
        speak(value.replace("{name}", NAME))
    elif kind == "url":
        speak("Opening that for you.")
        webbrowser.open(value)
    else:
        speak("That custom command has an unknown type.")


def h_add_command(text):
    phrase = ask("What phrase should trigger the new command?")
    if not phrase:
        speak("Okay, cancelled.")
        return True
    reply = ask(f"What should I say when you say {phrase}?")
    if not reply:
        speak("Okay, cancelled.")
        return True
    CONFIG["custom_commands"][phrase] = {"type": "say", "value": reply}
    save_config()
    speak(f"Done. When you say {phrase}, I will say: {reply}")
    return True


HANDLERS = {
    "greeting": h_greeting, "time": h_time, "date": h_date, "search": h_search,
    "open_site": h_open_site, "calculate": h_calculate, "joke": h_joke,
    "add_command": h_add_command, "help": h_help, "bye": h_bye, "knowledge": h_knowledge,
}


def handle(text):
    custom = match_custom(text)
    if custom:
        run_custom(custom)
        return True
    intent, score = parse_intent(text)
    if CONFIG.get("debug"):
        print(f"[intent: {intent} ({score:.2f})]")
    return HANDLERS[intent](text)


def main():
    speak(f"Voice assistant started. I'm {NAME}. Say hello to begin.")
    running = True
    while running:
        try:
            text = listen()
            if text:
                running = handle(text)
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except OSError as e:
            print(f"Microphone problem: {e}")
            speak("I can't access the microphone. Please check that it is connected and allowed.")
            break
        except Exception as e:
            print(f"Error: {e}")
            speak("Something went wrong. Let's try again.")


if __name__ == "__main__":
    main()