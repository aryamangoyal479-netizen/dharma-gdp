import discord
from discord.ext import commands
from discord import app_commands
import time

from groq import Groq
import openai

# ========================
# CONFIG
# ========================

DISCORD_TOKEN = "DISCORD_TOKEN"

GROQ_API_KEY = "GROQ_API_KEY"
ALT_API_KEY_1 = "ALT_API_KEY_1"
ALT_API_KEY_2 = "ALT_API_KEY_2"

# --- MODELS ---
MODEL_GROQ_TEXT = "llama-3.1-8b-instant"
MODEL_ALT_TEXT = "gpt-3.5-turbo"
MODEL_ALT_VISION = "gpt-4.1-mini"
MODEL_IMAGE_GEN = "gpt-image-1"

SYSTEM_PROMPT = "You are a helpful Discord AI assistant."

MAX_HISTORY = 6
COOLDOWN_SECONDS = 10
DISCORD_LIMIT = 1900

# ========================
# CLIENTS
# ========================

groq_client = Groq(api_key=GROQ_API_KEY)

openai_client_1 = openai.OpenAI(api_key=ALT_API_KEY_1)
openai_client_2 = openai.OpenAI(api_key=ALT_API_KEY_2)

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
    if len(text) > DISCORD_LIMIT:
        return text[:DISCORD_LIMIT] + "\n\n[Reply trimmed]"
    return text

# ========================
# MULTI-API FAILOVER (TEXT)
# ========================

def get_ai_reply(messages, temperature=0.2, max_tokens=300):
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

    try:
        completion = openai_client_1.chat.completions.create(
            model=MODEL_ALT_TEXT,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        print("✅ Using Alt API 1")
        return completion.choices[0].message.content
    except Exception as e:
        print("❌ Alt API 1 failed:", e)

    try:
        completion = openai_client_2.chat.completions.create(
            model=MODEL_ALT_TEXT,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        print("✅ Using Alt API 2")
        return completion.choices[0].message.content
    except Exception as e:
        print("❌ Alt API 2 failed:", e)

    return "❌ All AI providers are currently unavailable."

# ========================
# VISION (IMAGE UNDERSTANDING)
# ========================

def analyze_image_with_text(image_url, user_text):
    try:
        completion = openai_client_1.chat.completions.create(
            model=MODEL_ALT_VISION,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            max_tokens=300
        )
        print("🖼️ Using Alt API 1 Vision")
        return completion.choices[0].message.content
    except Exception as e:
        print("❌ Vision API 1 failed:", e)

    try:
        completion = openai_client_2.chat.completions.create(
            model=MODEL_ALT_VISION,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            max_tokens=300
        )
        print("🖼️ Using Alt API 2 Vision")
        return completion.choices[0].message.content
    except Exception as e:
        print("❌ Vision API 2 failed:", e)

    return "❌ Image analysis is currently unavailable."

# ========================
# IMAGE GENERATION
# ========================

def generate_image(prompt):
    try:
        result = openai_client_1.images.generate(
            model=MODEL_IMAGE_GEN,
            prompt=prompt,
            size="1024x1024"
        )
        print("🎨 Using Alt API 1 Image Gen")
        return result.data[0].url
    except Exception as e:
        print("❌ Image gen API 1 failed:", e)

    try:
        result = openai_client_2.images.generate(
            model=MODEL_IMAGE_GEN,
            prompt=prompt,
            size="1024x1024"
        )
        print("🎨 Using Alt API 2 Image Gen")
        return result.data[0].url
    except Exception as e:
        print("❌ Image gen API 2 failed:", e)

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
# PREFIX COMMAND (TEXT)
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
# SLASH COMMAND (TEXT)
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
        await interaction.followup.send("❌ Image generation failed.")

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
                reply = analyze_image_with_text(
                    img.url,
                    message.content or "Describe this image."
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