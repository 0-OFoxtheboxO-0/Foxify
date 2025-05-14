import discord
from discord.ext import commands
import os

bot = commands.Bot(command_prefix="!")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
