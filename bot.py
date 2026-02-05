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
HF_TOKEN = os.getenv("HF_TOKEN")  # HuggingFace token

# ================== SETTINGS ==================
AI_COOLDOWN = 8  # seconds per user
MAX_MEMORY = 6  # last messages per user
MAX_DISCORD_LENGTH = 1900
IMAGE_KEYWORDS = ["image", "draw", "picture", "illustrate", "art"]

# ================== BOT SET