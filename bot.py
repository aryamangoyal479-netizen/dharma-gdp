import discord
from discord.ext import commands
from groq import Groq
import os

# ========================
# CONFIG
# ========================

DISCORD_TOKEN = "DISCORD_TOKEN"
GROQ_API_KEY = "GROK"

MODEL_NAME = "llama-3.1-8b-instant"
  # fast + good on Groq
SYSTEM_PROMPT = "You are a helpful Discord AI assistant."

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
# EVENTS
# ========================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ========================
# COMMAND
# ========================

@bot.command(name="ai")
async def ai_chat(ctx, *, message: str):
    """Chat with AI using !ai"""
    try:
        await ctx.send("🤔 Thinking...")

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ],
            temperature=0.2,
            max_tokens=150
        )

        reply = completion.choices[0].message.content
        await ctx.send(reply)

    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# ========================
# MENTION / REPLY SUPPORT
# ========================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user in message.mentions or (
        message.reference
        and message.reference.resolved
        and message.reference.resolved.author == bot.user
    ):
        try:
            async with message.channel.typing():  # 👈 typing indicator
                completion = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": message.content}
                    ],
                    temperature=0.2,
                    max_tokens=150
                )

                reply = completion.choices[0].message.content
                await message.reply(reply)

        except Exception as e:
            await message.reply(f"❌ Error: {e}")

    await bot.process_commands(message)


# ========================
# RUN BOT
# ========================

bot.run(DISCORD_TOKEN)
