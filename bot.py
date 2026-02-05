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
bot.remove_command("help")  # remove default help command

# ================== MEMORY + COOLDOWN ==================
user_memory = defaultdict(lambda: deque(maxlen=MAX_MEMORY))
last_used = defaultdict(float)

def on_cooldown(user_id):
    return time.time() - last_used[user_id] < AI_COOLDOWN

def set_used(user_id):
    last_used[user_id] = time.time()

def trim(text):
    return text if len(text) <= MAX_DISCORD_LENGTH else text[:MAX_DISCORD_LENGTH] + "..."

# ================== TEXT AI ==================
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

# ================== IMAGE AI ==================
def call_image_ai(prompt):
    url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt}
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    image_path = f"image_{int(time.time())}.png"
    with open(image_path, "wb") as f:
        f.write(r.content)
    return image_path

# ================== AI ROUTER ==================
def get_ai_reply(user_id, prompt):
    messages = list(user_memory[user_id])
    messages.append({"role": "user", "content": prompt})

    if prompt.lower().startswith("generate image:"):
        # Extract prompt for image
        img_prompt = prompt[len("generate image:"):].strip()
        image_path = call_image_ai(img_prompt)
        user_memory[user_id].append({"role": "user", "content": prompt})
        user_memory[user_id].append({"role": "assistant", "content": f"[IMAGE GENERATED] {img_prompt}"})
        return image_path, "IMAGE"

    # Otherwise use text AI
    try:
        reply = call_groq(messages)
        provider = "Groq"
    except Exception:
        try:
            reply = call_gemini(prompt)
            provider = "Gemini"
        except Exception:
            try:
                reply = call_deepseek(prompt)
                provider = "DeepSeek"
            except Exception:
                reply = "❌ All text AI providers failed."
                provider = "None"

    # Save memory
    user_memory[user_id].append({"role": "user", "content": prompt})
    user_memory[user_id].append({"role": "assistant", "content": reply})
    return trim(reply), provider

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print("Commands loaded:")
    for cmd in bot.commands:
        print("-", cmd.name)

# ================== MAIN PREFIX COMMAND ==================
@bot.command(name="ai")
async def ai_command(ctx, *, prompt: str):
    user_id = ctx.author.id
    if on_cooldown(user_id):
        await ctx.send("⏳ Cooldown active. Please wait a few seconds.")
        return

    set_used(user_id)
    await ctx.typing()

    try:
        result, provider = get_ai_reply(user_id, prompt)
        if provider == "IMAGE":
            await ctx.send(file=discord.File(result))
        else:
            await ctx.send(f"🤖 **({provider})**\n{result}")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# ================== RUN BOT ==================
bot.run(DISCORD_TOKEN)