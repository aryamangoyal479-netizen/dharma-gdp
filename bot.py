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

# ================== SETTINGS ==================
AI_COOLDOWN = 8  # seconds per user
MAX_MEMORY = 6  # messages per user

# ================== BOT ==================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== MEMORY + COOLDOWN ==================
user_memory = defaultdict(lambda: deque(maxlen=MAX_MEMORY))
last_used = defaultdict(float)

# ================== UTIL ==================
def on_cooldown(user_id):
    return time.time() - last_used[user_id] < AI_COOLDOWN

def set_used(user_id):
    last_used[user_id] = time.time()

def trim(text, limit=1900):
    return text if len(text) <= limit else text[:limit] + "..."

# ================== GROQ ==================
def call_groq(messages):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "temperature": 0.7
    }
    r = requests.post(url, headers=headers, json=data, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ================== GEMINI (TEXT FALLBACK) ==================
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    r = requests.post(url, json=data, timeout=30)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

# ================== DEEPSEEK (TEXT FALLBACK) ==================
def call_deepseek(prompt):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post(url, headers=headers, json=data, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ================== IMAGE (ALT ONLY) ==================
def call_image_ai(prompt):
    # Replace with real image API (Replicate, HuggingFace, OpenAI Images, etc)
    # Placeholder example:
    return f"https://dummyimage.com/512x512/111/fff.png&text={prompt.replace(' ', '+')}"

# ================== MAIN AI ROUTER ==================
def get_ai_reply(user_id, prompt):
    messages = list(user_memory[user_id])
    messages.append({"role": "user", "content": prompt})

    # Try Groq first
    try:
        reply = call_groq(messages)
        provider = "Groq"
    except Exception:
        try:
            reply = call_gemini(prompt)
            provider = "Gemini"
        except Exception:
            reply = call_deepseek(prompt)
            provider = "DeepSeek"

    # Save memory
    user_memory[user_id].append({"role": "user", "content": prompt})
    user_memory[user_id].append({"role": "assistant", "content": reply})

    return reply, provider

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print("Commands:", [c.name for c in bot.commands])

# ================== !ai COMMAND ==================
@bot.command(name="ai")
async def ai_command(ctx, *, prompt: str):
    user_id = ctx.author.id

    if on_cooldown(user_id):
        await ctx.send("⏳ Cooldown active. Please wait a few seconds.")
        return

    set_used(user_id)
    await ctx.typing()

    try:
        reply, provider = get_ai_reply(user_id, prompt)
        await ctx.send(f"🤖 **({provider})**\n{trim(reply)}")
    except Exception as e:
        await ctx.send(f"❌ All AI providers failed: {e}")

# ================== !imagine COMMAND ==================
@bot.command(name="imagine")
async def imagine_command(ctx, *, prompt: str):
    await ctx.typing()

    try:
        image_url = call_image_ai(prompt)
        await ctx.send(f"🖼️ **Prompt:** {prompt}")
        await ctx.send(image_url)
    except Exception as e:
        await ctx.send(f"❌ Image generation failed: {e}")

# ================== SLASH COMMANDS ==================
@bot.tree.command(name="ai", description="Chat with AI")
async def slash_ai(interaction: discord.Interaction, prompt: str):
    user_id = interaction.user.id

    if on_cooldown(user_id):
        await interaction.response.send_message("⏳ Cooldown active.", ephemeral=True)
        return

    set_used(user_id)
    await interaction.response.defer(thinking=True)

    try:
        reply, provider = get_ai_reply(user_id, prompt)
        await interaction.followup.send(f"🤖 **({provider})**\n{trim(reply)}")
    except Exception as e:
        await interaction.followup.send(f"❌ AI error: {e}")

@bot.tree.command(name="imagine", description="Generate an image")
async def slash_imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)

    try:
        image_url = call_image_ai(prompt)
        await interaction.followup.send(f"🖼️ **Prompt:** {prompt}\n{image_url}")
    except Exception as e:
        await interaction.followup.send(f"❌ Image error: {e}")

# ================== RUN ==================
bot.run(DISCORD_TOKEN)