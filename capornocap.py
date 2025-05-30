import aiohttp
import base64
import json
import random
import os
from PIL import Image, ImageFilter, ImageEnhance
from io import BytesIO
import discord
from discord import app_commands, Embed, Interaction, ButtonStyle, File
from discord.ext import commands
from discord.ui import View, Button

# Load config
config = {}
with open("config.txt", "r") as f:
    for line in f:
        line = line.strip()
        if line and "=" in line:
            key, value = line.split("=", 1)
            config[key] = value

DISCORD_TOKEN = config["DISCORD_TOKEN"]
GITHUB_TOKEN = config["GITHUB_TOKEN"]
E621_USERNAME = config["E621_USERNAME"]
E621_API_KEY = config["E621_API_KEY"]
OWNER_ID = int(config["OWNER_ID"])

REPO_NAME = "0-OFoxtheboxO-0/Theme"
FILE_PATH = "fun.json"
CURRENCY_FILE = "currency.json"

class CapOrFap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def load_currency(self):
        if not os.path.exists(CURRENCY_FILE):
            return {}
        with open(CURRENCY_FILE, "r") as f:
            return json.load(f)

    def save_currency(self, data):
        with open(CURRENCY_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def update_balance(self, user_id, amount):
        currency = self.load_currency()
        balance = round(currency.get(str(user_id), 0), 2)
        new_balance = round(balance + amount, 2)
        if new_balance < 0:
            return None
        currency[str(user_id)] = new_balance
        self.save_currency(currency)
        return new_balance

    @app_commands.command(name="spicygame", description="Guess if the image is NSFW or SFW. Win or lose your bet!")
    @app_commands.describe(source="Choose image source", tags="Search tags", bet="How much to bet")
    @app_commands.choices(source=[
        app_commands.Choice(name="e621", value="e621"),
        app_commands.Choice(name="rule34", value="rule34"),
    ])
    async def spicy_game(self, interaction: Interaction, source: app_commands.Choice[str], tags: str, bet: float):
        await interaction.response.defer()

        currency = self.load_currency()
        user_id = str(interaction.user.id)
        balance = currency.get(user_id, 0)

        if bet <= 0 or bet > balance:
            await interaction.followup.send(f"Invalid bet. Your balance is {balance}.")
            return

        outcome_type = random.choices(["nsfw", "sfw"], weights=[3, 1])[0]  # Make outcome biased
        post = await self.fetch_post(source.value, tags, outcome_type)
        if not post:
            await interaction.followup.send("No suitable posts found.")
            return

        image_url = post.get("file", {}).get("url") if source.value == "e621" else post.get("file_url")
        if not image_url:
            await interaction.followup.send("Post is missing a valid image URL.")
            return

        blurred_image = await self.blur_image(image_url)
        if blurred_image is None:
            await interaction.followup.send("Failed to blur the image.")
            return

        file = File(fp=blurred_image, filename="blurred.jpg")

        embed = Embed(title="Guess if it's NSFW or SFW", description=f"Tags: {tags}\nBet: {bet}")
        embed.set_image(url="attachment://blurred.jpg")

        view = self.GuessButtons(self, interaction.user.id, outcome_type, bet, image_url)
        await interaction.followup.send(embed=embed, file=file, view=view)

    class GuessButtons(View):
        def __init__(self, cog, user_id, correct_type, bet, image_url):
            super().__init__(timeout=30)
            self.cog = cog
            self.user_id = user_id
            self.correct_type = correct_type
            self.bet = bet
            self.image_url = image_url

        @discord.ui.button(label="NSFW", style=ButtonStyle.danger, custom_id="guess_nsfw")
        async def nsfw_button(self, interaction: Interaction, button: Button):
            await self.handle_guess(interaction, "nsfw")

        @discord.ui.button(label="SFW", style=ButtonStyle.success, custom_id="guess_sfw")
        async def sfw_button(self, interaction: Interaction, button: Button):
            await self.handle_guess(interaction, "sfw")

        async def handle_guess(self, interaction: Interaction, guess):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn't your game!", ephemeral=True)
                return

            if guess == self.correct_type:
                new_balance = self.cog.update_balance(self.user_id, self.bet)
                if new_balance is None:
                    await interaction.response.send_message("Balance error. Contact an admin.", ephemeral=True)
                    return
                result = f"Correct! You doubled your bet. New balance: {new_balance}"
            else:
                new_balance = self.cog.update_balance(self.user_id, -self.bet)
                if new_balance is None:
                    await interaction.response.send_message("Insufficient funds or balance error.", ephemeral=True)
                    return
                result = f"Wrong! You lost your bet. New balance: {new_balance}"

            embed = Embed(title="Result", description=result)
            embed.set_image(url=self.image_url)
            await interaction.response.edit_message(content=None, embed=embed, view=None)

    async def fetch_post(self, site: str, tags: str, rating_filter=None):
        query = tags.replace(" ", "+")
        if rating_filter and site == "e621":
            query += "+rating:safe" if rating_filter == "sfw" else "+-rating:safe"
        url = f"https://e621.net/posts.json?tags={query}&limit=100" if site == "e621" else f"https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&tags={query}&limit=100"
        headers = {
            "User-Agent": f"CapOrFapBot/1.0 ({E621_USERNAME})",
            "Authorization": f"Basic {base64.b64encode(f'{E621_USERNAME}:{E621_API_KEY}'.encode()).decode()}"
        } if site == "e621" else {}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                try:
                    data = await resp.json()
                except Exception:
                    return None
                posts = data.get("posts") if site == "e621" else data
                if not posts:
                    return None
                return random.choice(posts)

    async def blur_image(self, image_url):
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    return None
                try:
                    image_bytes = await resp.read()
                except Exception:
                    return None
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            enhancer = ImageEnhance.Brightness(image)
            darkened = enhancer.enhance(0.4)
            blurred = darkened.filter(ImageFilter.GaussianBlur(60))
            output = BytesIO()
            blurred.save(output, format="JPEG")
            output.seek(0)
            return output
        except Exception:
            return None

async def update_github_wallpaper(image_url: str):
    api_url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as resp:
            if resp.status != 200:
                raise Exception(f"GitHub GET failed: {resp.status}")
            current = await resp.json()

        sha = current["sha"]
        content_data = base64.b64decode(current["content"]).decode()
        json_data = json.loads(content_data)

        if "background" not in json_data:
            json_data["background"] = {}
        json_data["background"]["url"] = image_url

        new_content = base64.b64encode(json.dumps(json_data, indent=2).encode()).decode()
        update_data = {
            "message": f"Update CapOrFap's wallpaper to {image_url}",
            "content": new_content,
            "sha": sha
        }

        async with session.put(api_url, headers=headers, json=update_data) as resp:
            result = await resp.text()
            if resp.status not in [200, 201]:
                raise Exception(f"GitHub PUT failed: {resp.status} - {result}")
            print("GitHub update result:", result)

async def setup(bot):
    await bot.add_cog(CapOrFap(bot))
