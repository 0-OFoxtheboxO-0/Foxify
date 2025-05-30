import aiohttp
import base64
import json
import random
from discord import app_commands, Embed, Interaction, ButtonStyle
from discord.ext import commands
from discord.ui import View, Button
import os
from PIL import Image
from io import BytesIO
import discord

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

currency_path = "currency.json"
if not os.path.exists(currency_path):
    with open(currency_path, "w") as f:
        json.dump({}, f)

def load_balances():
    with open(currency_path, "r") as f:
        return json.load(f)

def save_balances(data):
    with open(currency_path, "w") as f:
        json.dump(data, f, indent=2)

def add_balance(user_id, amount):
    data = load_balances()
    data[str(user_id)] = data.get(str(user_id), 0) + amount
    save_balances(data)

def get_balance(user_id):
    data = load_balances()
    return data.get(str(user_id), 0)

def deduct_balance(user_id, amount):
    data = load_balances()
    if str(user_id) not in data or data[str(user_id)] < amount:
        return False
    data[str(user_id)] -= amount
    save_balances(data)
    return True

class TagBattle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tag_guess_settings = {}

    @app_commands.command(name="tagguess", description="Guess which tag was used!")
    @app_commands.describe(source="Choose image source", tag1="First tag", tag2="Second tag", bet="Optional bet amount")
    @app_commands.choices(source=[
        app_commands.Choice(name="e621", value="e621"),
        app_commands.Choice(name="rule34", value="rule34"),
    ])
    async def tagguess(self, interaction: Interaction, source: app_commands.Choice[str], tag1: str, tag2: str, bet: int = 0):
        await interaction.response.defer()
        site = source.value

        if bet > 0 and not deduct_balance(interaction.user.id, bet):
            await interaction.followup.send("You don't have enough money to place that bet.")
            return

        self.tag_guess_settings[interaction.user.id] = {
            "tag1": tag1,
            "tag2": tag2,
            "site": site,
            "bet": bet
        }

        await self.start_game(interaction, tag1, tag2, site, bet)

    async def start_game(self, interaction, tag1, tag2, site, bet):
        chosen_tag, hidden_tag = (tag1, f"-{tag2}") if random.choice([True, False]) else (tag2, f"-{tag1}")
        query = f"{chosen_tag} {hidden_tag}"
        post = await self.fetch_post(site, query)

        if not post:
            if bet > 0:
                add_balance(interaction.user.id, bet)
            await interaction.followup.send("No results found. Your bet has been refunded.")
            return

        image_url = post.get("file", {}).get("url") if site == "e621" else post.get("file_url")
        if not image_url:
            if bet > 0:
                add_balance(interaction.user.id, bet)
            await interaction.followup.send("Couldn't load the image. Your bet has been refunded.")
            return

        cropped_image = await self.crop_image(image_url, 0.05)
        if not cropped_image:
            if bet > 0:
                add_balance(interaction.user.id, bet)
            await interaction.followup.send("Failed to process image. Your bet has been refunded.")
            return

        self.tag_guess_settings[interaction.user.id].update({
            "correct_tag": chosen_tag,
            "image_url": image_url,
            "hint_used": False
        })

        embed = Embed(title="Tag Guess Game", description="Guess which tag was **not** negated!")
        file = discord.File(cropped_image, filename="cropped.jpg")
        embed.set_image(url="attachment://cropped.jpg")
        view = self.build_tag_view(interaction.user.id, tag1, tag2)
        await interaction.followup.send(embed=embed, file=file, view=view)

    async def fetch_post(self, site: str, tags: str):
        query = tags.replace(" ", "+")
        try:
            if site == "e621":
                url = f"https://e621.net/posts.json?tags={query}&limit=100"
                headers = {
                    "User-Agent": f"FoxifyBot/1.0 ({E621_USERNAME})",
                    "Authorization": f"Basic {base64.b64encode(f'{E621_USERNAME}:{E621_API_KEY}'.encode()).decode()}"
                }
            else:
                url = f"https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&tags={query}&limit=100"
                headers = {}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    posts = data.get("posts") if site == "e621" else data
                    if not posts:
                        return None
                    return random.choice(posts)
        except Exception as e:
            print(f"[ERROR] fetch_post failed: {e}")
            return None

    async def crop_image(self, url: str, crop_ratio: float):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    image_data = await resp.read()

            img = Image.open(BytesIO(image_data))
            width, height = img.size
            crop_width = int(width * crop_ratio)
            crop_height = int(height * crop_ratio)

            left = random.randint(0, width - crop_width)
            top = random.randint(0, height - crop_height)
            cropped = img.crop((left, top, left + crop_width, top + crop_height))

            buffer = BytesIO()
            cropped.save(buffer, format="JPEG")
            buffer.seek(0)
            return buffer
        except Exception as e:
            print(f"[ERROR] crop_image failed: {e}")
            return None

    def build_tag_view(self, user_id, tag1, tag2):
        view = View(timeout=None)
        game = self.tag_guess_settings[user_id]
        cog = self

        class TagGuessButton(Button):
            def __init__(self, label_tag):
                super().__init__(label=label_tag, style=ButtonStyle.primary)
                self.tag_choice = label_tag

            async def callback(self, interaction: Interaction):
                game_data = cog.tag_guess_settings.get(user_id)
                if not game_data:
                    await interaction.response.send_message("No active game found.", ephemeral=True)
                    return

                correct = game_data["correct_tag"]
                bet = game_data["bet"]
                hint_used = game_data["hint_used"]

                if self.tag_choice == correct:
                    multiplier = 1.5 if hint_used else 2
                    winnings = int(bet * multiplier)
                    add_balance(user_id, winnings)
                    msg = f"Correct! You chose **{self.tag_choice}**. You won {winnings}¥."
                else:
                    loss = int(bet * 0.5) if hint_used else 0
                    if loss:
                        deduct_balance(user_id, loss)
                    msg = f"Wrong! The correct tag was **{correct}**. You lost your bet.{" An additional 50% was deducted for using a hint." if hint_used else ""}"

                image_url = game_data["image_url"]
                embed = Embed(title="Full Image Revealed")
                embed.set_image(url=image_url)
                await interaction.response.send_message(msg, embed=embed, view=NextGameView(user_id, cog))

        class HintButton(Button):
            def __init__(self):
                super().__init__(label="Hint", style=ButtonStyle.secondary)

            async def callback(self, interaction: Interaction):
                game_data = cog.tag_guess_settings.get(user_id)
                if not game_data:
                    await interaction.response.send_message("No active game found.", ephemeral=True)
                    return
                game_data["hint_used"] = True
                new_cropped = await cog.crop_image(game_data["image_url"], 0.1)
                if not new_cropped:
                    await interaction.response.send_message("Hint image failed to load.", ephemeral=True)
                    return
                embed = Embed(title="Hint Image (10%)")
                file = discord.File(new_cropped, filename="hint.jpg")
                embed.set_image(url="attachment://hint.jpg")
                await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

        view.add_item(TagGuessButton(tag1))
        view.add_item(TagGuessButton(tag2))
        view.add_item(HintButton())
        return view

class NextGameView(View):
    def __init__(self, user_id, cog):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.cog = cog
        self.add_item(self.NextGameButton(cog))

    class NextGameButton(Button):
        def __init__(self, cog):
            super().__init__(label="Next Game", style=ButtonStyle.success)
            self.cog = cog

        async def callback(self, interaction: Interaction):
            game_data = self.cog.tag_guess_settings.get(interaction.user.id)
            if not game_data:
                await interaction.response.send_message("No active game data found to start next game.", ephemeral=True)
                return

            await self.cog.start_game(
                interaction,
                game_data["tag1"],
                game_data["tag2"],
                game_data["site"],
                game_data["bet"]
            )

async def setup(bot):
    await bot.add_cog(TagBattle(bot))

