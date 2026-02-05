import os
import time
import discord
from discord.ext import commands
from collections import defaultdict, deque
import requests

# ================== ENV ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")  # HuggingFace API token

# ================== SETTINGS ==================
AI_COOLDOWN = 8  # seconds per user
MAX_MEMORY = 6   # last messages per user

# ================== BOT SETUP ==================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

# ================== MEMORY + COOLDOWN ==================
user_memory = defaultdict(lambda: deque(maxlen=MAX_MEMORY))
last_used = defaultdict(float)

def on_cooldown(user_id):
    return time.time() - last_used[user_id] < AI_COOLDOWN

def set_used(user_id):
    last_used[user_id] = time.time()

def trim(text):
    return text if len(text) <= 1900 else text[:1900] + "..."

# ================== TEXT AI FUNCTIONS ==================
def call_groq(messages):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "llama-3.1-8b-instant", "messages": messages, "temperature": 0.7}
    r = requests.post(url, headers=headers, json=data, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(url, json=data, timeout=30)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def call_deepseek(prompt):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}]}
    r = requests.post(url, headers=headers, json=data, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def call_huggingface(prompt):
    url = "https://api-inference.huggingface.co/models/gpt2"  # Example text model
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 200}}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    output = r.json()
    # HuggingFace sometimes returns a list of dicts
    if isinstance(output, list):
        return output[0]["generated_text"]
    return str(output)

# ================== AI ROUTER ==================
def get_ai_reply(user_id, prompt):
    messages = list(user_memory[user_id])
    messages.append({"role": "user", "content": prompt})

    # Try Groq first
    try:
        reply = call_groq(messages)
    except Exception:
        try:
            reply = call_gemini(prompt)
        except Exception:
            try:
                reply = call_deepseek(prompt)
            except Exception:
                try:
                    reply = call_huggingface(prompt)
                except Exception:
                    reply = "❌ All text AI providers failed."

    # Save memory
    user_memory[user_id].append({"role": "user", "content": prompt})
    user_memory[user_id].append({"role": "assistant", "content": reply})
    return trim(reply)

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print("Bot is ready!")

# ================== PREFIX COMMAND ==================
@bot.command(name="ai")
async def ai_command(ctx, *, prompt: str):
    user_id = ctx.author.id
    if on_cooldown(user_id):
        await ctx.send("⏳ Cooldown active. Please wait a few seconds.")
        return

    set_used(user_id)
    async with ctx.typing():
        try:
            result = get_ai_reply(user_id, prompt)
            await ctx.send(result)
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

# ================== MENTION & REPLY HANDLER ==================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Let prefix commands like !ai still work
    if message.content.startswith("!ai"):
        await bot.process_commands(message)
        return

    # Respond if bot is mentioned or replied to
    if bot.user in message.mentions or message.reference:
        user_id = message.author.id
        prompt = message.content
        if on_cooldown(user_id):
            await message.channel.send("⏳ Cooldown active. Please wait a few seconds.")
            return

        set_used(user_id)
        async with message.channel.typing():
            try:
                result = get_ai_reply(user_id, prompt)
                await message.channel.send(result)
            except Exception as e:
                await message.channel.send(f"❌ Error: {e}")

# ================== RUN BOT ==================
bot.run(DISCORD_TOKEN)