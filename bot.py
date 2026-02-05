import os
import time
import discord
from discord.ext import commands
from collections import defaultdict, deque
import requests

# ================== ENV ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")  # HuggingFace token

# ================== SETTINGS ==================
AI_COOLDOWN = 8  # seconds per user
MAX_MEMORY = 6  # last messages per user
MAX_DISCORD_LENGTH = 1900

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
    return text if len(text) <= MAX_DISCORD_LENGTH else text[:MAX_DISCORD_LENGTH] + "..."

# ================== IMAGE AI ==================
def call_huggingface(prompt):
    url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt}
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    image_path = f"image_{int(time.time())}.png"
    with open(image_path, "wb") as f:
        f.write(r.content)
    return image_path

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print("Commands loaded:")
    for cmd in bot.commands:
        print("-", cmd.name)

# ================== PREFIX COMMAND ==================
@bot.command(name="ai")
async def ai_command(ctx, *, prompt: str):
    user_id = ctx.author.id
    if on_cooldown(user_id):
        await ctx.send("⏳ Cooldown active. Please wait a few seconds.")
        return

    set_used(user_id)
    user_memory[user_id].append(prompt)

    # Typing indicator while generating
    async with ctx.typing():
        try:
            image_path = call_huggingface(prompt)
            await ctx.send(f"🖼️ **Prompt:** {prompt}")
            await ctx.send(file=discord.File(image_path))
        except Exception as e:
            await ctx.send(f"❌ Image generation failed: {e}")

# ================== RUN BOT ==================
bot.run(DISCORD_TOKEN)