import os
import discord
from discord.ext import commands

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print("Commands loaded:")
    for cmd in bot.commands:
        print("-", cmd.name)

@bot.command(name="imagine")
async def imagine(ctx, *, prompt: str):
    await ctx.send(f"Imagine command received: {prompt}")

bot.run(DISCORD_TOKEN)