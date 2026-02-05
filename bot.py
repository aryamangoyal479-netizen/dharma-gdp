import discord
from discord.ext import commands
import time
import aiohttp

from groq import Groq
import google.generativeai as genai
from openai import OpenAI   # For DeepSeek (OpenAI-compatible)

# ========================
# CONFIG
# ========================

DISCORD_TOKEN = "DISCORD_TOKEN"

GROQ_API_KEY = "GROQ_API_KEY"
ALT_API_KEY_1 = "ALT_API_KEY_1"   # GEMINI KEY
ALT_API_KEY_2 = "ALT_API_KEY_2"   # DEEPSEEK KEY

MODEL_GROQ_TEXT = "llama-3.1-8b-instant"

SYSTEM_PROMPT = "You are a helpful Discord AI assistant."

MAX_HISTORY = 6
COOLDOWN_SECONDS = 10
DISCORD_LIMIT = 1900

# ========================
# CLIENTS
# ========================

# Groq
groq_client = Groq(api_key=GROQ_API_KEY)

# Gemini
genai.configure(api_key=ALT_API_KEY_1)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# DeepSeek (OpenAI compatible)
deepseek_client = OpenAI(
    api_key=ALT_API_KEY_2,
    base_url="https://api.deepseek.com"
)

# ========================
# DISCORD SETUP
# ========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========================
# MEMORY + COOLDOWN
# ========================

user_memory = {}
user_cooldowns = {}

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

    if len(user_memory[user_id]) > MAX_HISTORY:
        user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

def build_messages(user_id, user_message):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if user_id in user_memory:
        messages.extend(user_memory[user_id])

    messages.append({"role": "user", "content": user_message})
    return messages

def trim_reply(text):
    if not text:
        return "❌ Empty response from AI."
    if len(text) > DISCORD_LIMIT:
        return text[:DISCORD_LIMIT] + "\n\n[Reply trimmed]"
    return text

# ========================
# MULTI-API FAILOVER (TEXT)
# ========================

def get_ai_reply(messages, temperature=0.2, max_tokens=300):
    # ---- TRY GROQ ----
    try:
        completion = groq_client.chat.completions.create(
            model=MODEL_GROQ_TEXT,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        print("✅ Using Groq")
        return completion.choices[0].message.content
    except Exception as e:
        print("❌ Groq failed:", e)

    # ---- TRY GEMINI ----
    try:
        prompt = "\n".join([m["content"] for m in messages if m["role"] != "system"])
        response = gemini_model.generate_content(prompt)
        print("✅ Using Gemini")
        return response.text
    except Exception as e:
        print("❌ Gemini failed:", e)

    # ---- TRY DEEPSEEK ----
    try:
        completion = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        print("✅ Using DeepSeek")
        return completion.choices[0].message.content
    except Exception as e:
        print("❌ DeepSeek failed:", e)

    return "❌ All AI providers are currently unavailable."

# ========================
# IMAGE UNDERSTANDING (GEMINI VISION)
# ========================

async def analyze_image_with_text(image_url, user_text):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                img_bytes = await resp.read()

        response = gemini_model.generate_content([
            user_text or "Describe this image.",
            {
                "mime_type": "image/jpeg",
                "data": img_bytes
            }
        ])

        print("🖼️ Using Gemini Vision")
        return response.text

    except Exception as e:
        print("❌ Gemini Vision failed:", e)
        return "❌ Image analysis is currently unavailable."

# ========================
# IMAGE GENERATION (PLACEHOLDER)
# ========================

def generate_image(prompt):
    # Gemini does NOT reliably return image URLs via API.
    # This is a placeholder so your bot doesn't crash.
    return None

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
# PREFIX COMMAND
# ========================

@bot.command(name="ai")
async def ai_chat(ctx, *, message: str):
    user_id = ctx.author.id

    if is_on_cooldown(user_id):
        await ctx.send("⏳ Slow down!")
        return

    async with ctx.typing():
        messages = build_messages(user_id, message)
        reply = get_ai_reply(messages)
        reply = trim_reply(reply)

        add_to_memory(user_id, "user", message)
        add_to_memory(user_id, "assistant", reply)

        set_cooldown(user_id)
        await ctx.send(reply)

# ========================
# SLASH COMMAND
# ========================

@bot.tree.command(name="ai", description="Chat with the AI")
async def slash_ai(interaction: discord.Interaction, message: str):
    user_id = interaction.user.id

    if is_on_cooldown(user_id):
        await interaction.response.send_message("⏳ Slow down!", ephemeral=True)
        return

    await interaction.response.defer()

    messages = build_messages(user_id, message)
    reply = get_ai_reply(messages)
    reply = trim_reply(reply)

    add_to_memory(user_id, "user", message)
    add_to_memory(user_id, "assistant", reply)

    set_cooldown(user_id)
    await interaction.followup.send(reply)

# ========================
# SLASH COMMAND (IMAGE GEN)
# ========================

@bot.tree.command(name="imagine", description="Generate an image from a prompt")
async def imagine(interaction: discord.Interaction, prompt: str):
    user_id = interaction.user.id

    if is_on_cooldown(user_id):
        await interaction.response.send_message("⏳ Slow down!", ephemeral=True)
        return

    await interaction.response.defer()

    image_url = generate_image(prompt)
    set_cooldown(user_id)

    if image_url:
        await interaction.followup.send(f"🎨 **Prompt:** {prompt}\n{image_url}")
    else:
        await interaction.followup.send(
            "⚠️ Image generation is not fully supported with Gemini API.\n"
            "Use another provider (OpenAI, Stability, Replicate) for real image gen."
        )

# ========================
# MENTION / REPLY + IMAGE VISION
# ========================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    is_trigger = (
        bot.user in message.mentions or
        (
            message.reference and
            message.reference.resolved and
            message.reference.resolved.author == bot.user
        )
    )

    if is_trigger:
        user_id = message.author.id

        if is_on_cooldown(user_id):
            await message.reply("⏳ Slow down!")
            return

        async with message.channel.typing():

            # ---- IF IMAGE ATTACHED (VISION) ----
            if message.attachments:
                img = message.attachments[0]
                reply = await analyze_image_with_text(
                    img.url,
                    message.content
                )
                reply = trim_reply(reply)
                set_cooldown(user_id)
                await message.reply(reply)
                return

            # ---- NORMAL TEXT ----
            messages = build_messages(user_id, message.content)
            reply = get_ai_reply(messages)
            reply = trim_reply(reply)

            add_to_memory(user_id, "user", message.content)
            add_to_memory(user_id, "assistant", reply)

            set_cooldown(user_id)
            await message.reply(reply)

    await bot.process_commands(message)

# ========================
# RUN
# ========================

bot.run(DISCORD_TOKEN)