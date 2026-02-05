import os
import time
import discord
from discord.ext import commands
import requests
from collections import defaultdict, deque

# ================== ENV ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")  # HuggingFace

# ================== SETTINGS ==================
AI_COOLDOWN = 8  # seconds per user
MAX_MEMORY = 6  # messages per user
MAX_DISCORD_LENGTH = 1900

# ================== BOT SETUP ==================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================== MEMORY + COOLDOWN ==================
user_memory = defaultdict(lambda: deque(maxlen=MAX_MEMORY))
last_used = defaultdict(float)

# ================== UTILS ==================
def on_cooldown(user_id):
    return time.time() - last_used[user_id] < AI_COOLDOWN

def set_used(user_id):
    last_used[user_id] = time