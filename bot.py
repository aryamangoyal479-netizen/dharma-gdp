import discord
from discord.ext import commands
from discord import app_commands
from groq import Groq
import time

# ========================
# CONFIG
# ========================

DISCORD_TOKEN = "DISCORD_TOKEN"
GROQ_API_KEY = "GROQ_API_KEY"

MODEL_NAME = "llama-3.1-8b-instant"
SYSTEM_PROMPT = "You are a helpful Discord AI assistant."

MAX_HISTORY = 6          # messages kept per user
COOLDOWN_SECONDS = 10    # per user cooldown
DISCORD_LIMIT = 1900     # safe message limit

# ========================
# DISCORD SETUP
# ========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========================
# GROQ CLIENT
# ========================

client = Groq(api_key=GROQ_API_KEY)

# ========================
# MEMORY + COOLDOWN
# ========================

user_memory = {}      # user_id -> list of messages
user_cooldowns = {}  # user_id -> last_used_time

# ========================
# UTILS
# ========================

def is_on_cooldown(user_id):
    now = time.time()
    last = user_cooldowns.get(user_id, 0)
    return (now - last) < COOLDOWN_SECONDS

def set_cooldown(user_id):
    user_cooldowns[user_id] = time.time()

def add_to_memory(user_id, role, content):
    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({"role": role, "content": content})

    # Trim history
    if len(user_memory[user_id]) > MAX_HISTORY:
        user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

def build_messages(user_id, user_message):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if user_id in user_memory:
        messages.extend(user_memory[user_id])

    messages.append({"role": "user", "content": user_message})
    return messages

def trim_reply(text):
    if len(text) > DISCORD_LIMIT:
        return text[:DISCORD_LIMIT] + "\n\n[Reply trimmed]"
    return text

# ========================
# EVENTS
# ========================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print("Slash sync error:", e)

# ========================
# PREFIX COMMAND (!ai)
# ========================

@bot.command(name="ai")
async def ai_chat(ctx, *, message: str):
    user_id = ctx.author.id

    if is_on_cooldown(user_id):
        await ctx.send("⏳ Slow down! Please wait a few seconds.")
        return

    try:
        async with ctx.typing():
            messages = build_messages(user_id, message)

            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.2,
                max_tokens=200
            )

            reply = completion.choices[0].message.content
            reply = trim_reply(reply)

            # Save memory
            add_to_memory(user_id, "user", message)
            add_to_memory(user_id, "assistant", reply)

            set_cooldown(user_id)
            await ctx.send(reply)

    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# ========================
# SLASH COMMAND (/ai)
# ========================

@bot.tree.command(name="ai", description="Chat with the AI")
@app_commands.describe(message="Your message to the AI")
async def slash_ai(interaction: discord.Interaction, message: str):
    user_id = interaction.user.id

    if is_on_cooldown(user_id):
        await interaction.response.send_message(
            "⏳ Slow down! Please wait a few seconds.",
            ephemeral=True
        )
        return

    await interaction
