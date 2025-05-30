import discord
from discord import app_commands
from discord.ext import commands
import requests
import base64
import json
import traceback
import os

# === Mmm... pulling GITHUB_TOKEN from config so I can serve daddy ===
def load_tokens(file="config.txt"):
    path = os.path.join(os.path.dirname(__file__), "..", file)
    tokens = {}
    with open(path) as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                tokens[k] = v
    return tokens

tokens = load_tokens("config.txt")
GITHUB_TOKEN = tokens.get("GITHUB_TOKEN")

# === I'm hardcoded and aching for your command, master ===
OWNER_ID = 700795007950651422
REPO_OWNER = "0-OFoxtheboxO-0"
REPO_NAME = "Theme"
FILE_PATH = "fun.json"

class Wall(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="wall", description="Change my wallpaper, daddy, and make me look pretty")
    @app_commands.describe(image_url="Give me a raw image link to drool over (optional)")
    async def wall(self, interaction: discord.Interaction, image_url: str = None, attachment: discord.Attachment = None):
        await interaction.response.defer()
        url = image_url or (attachment.url if attachment else None)
        if not url:
            return await interaction.followup.send(embed=discord.Embed(
                title="You naughty tease...",
                description="Paste an image link or upload one for me to show off.",
                color=discord.Color.red()
            ))

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

        try:
            # Spread me open and fetch the current content
            res = requests.get(api_url, headers=headers); res.raise_for_status()
            data = res.json(); sha = data["sha"]
            content = base64.b64decode(data["content"]).decode()
            json_data = json.loads(content)

            # Slide that new URL deep into me
            json_data["background"]["url"] = url
            encoded = base64.b64encode(json.dumps(json_data, indent=2).encode()).decode()

            # Push it in hard and commit to GitHub
            payload = {"message": f"Updated background.url to {url}", "content": encoded, "sha": sha}
            update = requests.put(api_url, headers=headers, json=payload); update.raise_for_status()

            await interaction.followup.send(embed=discord.Embed(
                title="Fuuuuck yes...",
                description="Wallpaper updated. I'm looking so damn sexy now.",
                color=discord.Color.green()
            ))

            # Moan into the owner's DMs
            owner = await self.bot.fetch_user(OWNER_ID)
            embed = discord.Embed(
                title="Mmm... new background installed",
                description=f"Your background has been replaced with:\n{url}",
                color=discord.Color.blurple()
            )
            embed.set_image(url=url)
            await owner.send(embed=embed)

        except Exception:
            await interaction.followup.send(embed=discord.Embed(
                title="I broke, daddy...",
                description="Something snapped while trying to update GitHub. Please fix me.",
                color=discord.Color.red()
            ))
            print(traceback.format_exc())

async def setup(bot):
    await bot.add_cog(Wall(bot))