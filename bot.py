import os
import discord
from discord.ext import commands
import aiohttp

# =====================
# CONFIG
# =====================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ALT_IMAGE_API_KEY = os.getenv("ALT_IMAGE_API_KEY")  # for image gen

TEXT_COOLDOWN_SECONDS = 5

# =====================
# DISCORD SETUP
# =====================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

user_cooldowns = {}

# =====================
# UTILS
# =====================

def is_on_cooldown(user_id):
    import time
    now = time.time()
    last = user_cooldowns.get(user_id, 0)
    if now - last < TEXT_COOLDOWN_SECONDS:
        return True
    user_cooldowns[user_id] = now
    return False

def trim_for_discord(text, limit=1900):
    if len(text) > limit:
        return text[:limit] + "\n\n✂️ *Reply trimmed*"
    return text

# =====================
# TEXT AI (GROQ EXAMPLE)
# =====================

async def call_text_ai(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            return data["choices"][0]["message"]["content"]

# =====================
# IMAGE AI (PLACEHOLDER)
# =====================

async def generate_image(prompt):
    # 🔴 REPLACE THIS WITH YOUR REAL IMAGE API
    # Example: Gemini, DeepSeek, Replicate, etc.

    # For now, return dummy image
    return "https://picsum.photos/512"

# =====================
# EVENTS
# =====================

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # IMPORTANT: Prevent auto AI from replying to commands
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    # OPTIONAL: Auto AI reply (if you want)
    # Comment this out if you DON'T want auto replies
    """
    if is_on_cooldown(message.author.id):
        return

    await message.channel.typing()
    try:
        reply = await call_text_ai(message.content)
        reply = trim_for_discord(reply)
        await message.reply(reply)
    except Exception as e:
        await message.reply(f"❌ AI Error: {e}")
    """

# =====================
# COMMANDS
# =====================

@bot.command()
async def ai(ctx, *, prompt: str):
    if is_on_cooldown(ctx.author.id):
        await ctx.send("⏳ Slow down bro, cooldown active.")
        return

    await ctx.typing()

    try:
        reply = await call_text_ai(prompt)
        reply = trim_for_discord(reply)
        await ctx.send(reply)
    except Exception as e:
        await ctx.send(f"❌ AI Error: {e}")

@bot.command()
async def imagine(ctx, *, prompt: str):
    await ctx.typing()

    try:
        image_url = await generate_image(prompt)

        await ctx.send(f"🖼️ **Prompt:** {prompt}")
        await ctx.send(image_url)

    except Exception as e:
        await ctx.send(f"❌ Image generation failed: {e}")

# =====================
# RUN
# =====================

bot.run(DISCORD_TOKEN)