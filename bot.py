import os
import time
import discord
from discord.ext import commands
from discord import app_commands

import requests

# ========================
# CONFIG
# ========================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")      # optional
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")  # optional

MAX_HISTORY = 6
COOLDOWN_SECONDS = 10
DISCORD_CHAR_LIMIT = 1900

# ========================
# MEMORY + COOLDOWN
# ========================

user_memory = {}
user_cooldowns = {}

# ========================
# DISCORD SETUP
# ========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ========================
# AI HELPERS
# ========================

def trim_text(text):
    if len(text) > DISCORD_CHAR_LIMIT:
        return text[:DISCORD_CHAR_LIMIT] + "\n\n... (trimmed)"
    return text


def groq_chat(messages):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.1-8b-instant",
        "messages": messages
    }

    r = requests.post(url, headers=headers, json=data, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def gemini_chat(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    r = requests.post(url, json=data, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def deepseek_chat(prompt):
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}]
    }

    r = requests.post(url, headers=headers, json=data, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_text_ai(messages):
    # Try Groq → Gemini → DeepSeek
    try:
        return groq_chat(messages)
    except:
        pass

    try:
        if GEMINI_API_KEY:
            prompt = messages[-1]["content"]
            return gemini_chat(prompt)
    except:
        pass

    try:
        if DEEPSEEK_API_KEY:
            prompt = messages[-1]["content"]
            return deepseek_chat(prompt)
    except:
        pass

    return "❌ All AI APIs failed or quota exceeded."


def generate_image_alt(prompt):
    # Example placeholder (replace with real image API if you want)
    # You can connect to any free image API here
    return f"🖼️ Image generation request received for:\n**{prompt}**\n(Connect your image API here)"

# ========================
# SLASH COMMAND
# ========================

@bot.tree.command(name="ai", description="Chat with AI")
@app_commands.describe(prompt="Your message to AI")
async def ai(interaction: discord.Interaction, prompt: str):

    user_id = interaction.user.id
    now = time.time()

    # Cooldown
    if user_id in user_cooldowns:
        if now - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            await interaction.response.send_message(
                f"⏳ Cooldown! Wait {COOLDOWN_SECONDS} seconds.",
                ephemeral=True
            )
            return

    user_cooldowns[user_id] = now

    await interaction.response.defer(thinking=False)
    await interaction.channel.typing()

    # Init memory
    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": "user", "content": prompt})
    user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

    # IMAGE MODE (ONLY ALT AI)
    if "make image" in prompt.lower() or "generate image" in prompt.lower():
        reply = generate_image_alt(prompt)

    else:
        messages = [{"role": "system", "content": "You are a helpful Discord AI bot."}]
        messages.extend(user_memory[user_id])

        reply = call_text_ai(messages)

    user_memory[user_id].append({"role": "assistant", "content": reply})
    user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

    reply = trim_text(reply)

    await interaction.followup.send(reply)

# ========================
# EVENTS
# ========================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# ========================
# START BOT
# ========================

bot.run(DISCORD_TOKEN)