import os
import discord
from discord.ext import commands
import requests
from collections import defaultdict, deque
import time

# ===== ENV =====
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")  # HuggingFace

# ===== SETTINGS =====
AI_COOLDOWN = 8
MAX_MEMORY = 6
MAX_DISCORD_LENGTH = 1900

# ===== BOT =====
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

# ===== MEMORY =====
user_memory = defaultdict(lambda: deque(maxlen=MAX_MEMORY))
last_used = defaultdict(float)

def on_cooldown(user_id):
    return time.time() - last_used[user_id] < AI_COOLDOWN

def set_used(user_id):
    last_used[user_id] = time.time()

def trim(text):
    return text if len(text) <= MAX_DISCORD_LENGTH else text[:MAX_DISCORD_LENGTH] + "..."

# ===== IMAGE =====
def call_image_ai(prompt):
    url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt}
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    with open("image.png", "wb") as f:
        f.write(r.content)
    return "image.png"

# ===== COMMANDS =====
@bot.command(name="ai")
async def ai_command(ctx, *, prompt: str):
    user_id = ctx.author.id
    if on_cooldown(user_id):
        await ctx.send("⏳ Cooldown active.")
        return
    set_used(user_id)
    await ctx.typing()
    reply = f"Echo AI: {prompt}"  # Replace with real API call
    user_memory[user_id].append({"role": "user", "content": prompt})
    user_memory[user_id].append({"role": "assistant", "content": reply})
    await ctx.send(trim(reply))

@bot.command(name="imagine")
async def imagine_command(ctx, *, prompt: str):
    await ctx.typing()
    try:
        image_path = call_image_ai(prompt)
        await ctx.send(f"🖼️ Prompt: {prompt}")
        await ctx.send(file=discord.File(image_path))
    except Exception as e:
        await ctx.send(f"❌ Image error: {e}")

# ===== READY =====
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print("Commands loaded:")
    for cmd in bot.commands:
        print("-", cmd.name)

# ===== RUN =====
bot.run(DISCORD_TOKEN)