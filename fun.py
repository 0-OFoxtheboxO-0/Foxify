import aiohttp
import base64
import json
import random
from discord import app_commands, Embed, Interaction, ButtonStyle
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import os

# Spreading config.txt wide open for daddy’s tokens
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

# Mmm, setting up my balance hole for lewd tokens
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

class HornyFun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @app_commands.command(name="highlow", description="Guess how much the internet came just looking at this pic")
    @app_commands.describe(source="Where the lewdness comes from", tags="Kinks to search for", bet="How much you wanna gamble, baby?")
    @app_commands.choices(source=[
        app_commands.Choice(name="e621", value="e621"),
        app_commands.Choice(name="rule34", value="rule34"),
    ])
    async def highlow(self, interaction: Interaction, source: app_commands.Choice[str], tags: str = "", bet: int = 0):
        await interaction.response.defer()
        site = source.value

        if bet > 0 and not deduct_balance(interaction.user.id, bet):
            await interaction.followup.send("Not enough porn coins to play, slut.")
            return

        post = await self.fetch_post(site, tags)
        if not post:
            await interaction.followup.send("No filthy results found... sad and horny.")
            return

        score = post["score"]["total"] if site == "e621" else int(post.get("score", 0))
        image_url = post["file"]["url"] if site == "e621" else post["file_url"]

        self.active_games[interaction.user.id] = {
            "score": score,
            "guesses": 0,
            "bet": bet,
            "site": site,
            "tags": tags,
            "image_url": image_url
        }

        embed = Embed(title=f"Guess how hot this is! Source: {site}", description=f"Tags: {tags}\nGuesses: 0")
        embed.set_image(url=image_url)

        view = await self.build_view(interaction.user.id)
        await interaction.followup.send(embed=embed, view=view)

    async def fetch_post(self, site: str, tags: str):
        query = tags.replace(" ", "+")
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
                try:
                    data = await resp.json()
                except Exception:
                    return None
                posts = data.get("posts") if site == "e621" else data
                if not posts:
                    return None
                return random.choice(posts)

    async def build_view(self, user_id):
        view = View(timeout=None)
        cog = self
        game = self.active_games[user_id]

        class GuessScoreButton(Button):
            def __init__(self):
                super().__init__(label="Guess That Score, Bitch", style=ButtonStyle.success)

            async def callback(self, i: Interaction):
                class GuessModal(Modal, title="Take a guess, slut"):
                    guess = TextInput(label="How hot is it?", placeholder="Drop a number... big or small")

                    async def on_submit(self, modal_interaction: Interaction):
                        current_game = cog.active_games.get(user_id)
                        if not current_game:
                            await modal_interaction.response.send_message("No dirty game running.", ephemeral=True)
                            return

                        try:
                            guessed = int(self.guess.value.strip())
                        except ValueError:
                            await modal_interaction.response.send_message("That's not a number, you horny fool.", ephemeral=True)
                            return

                        current_game["guesses"] += 1

                        if guessed == current_game["score"]:
                            multiplier = max(0, 7 - current_game["guesses"])
                            winnings = current_game["bet"] * multiplier if multiplier > 0 else 0
                            if winnings > 0:
                                add_balance(user_id, winnings)
                            await modal_interaction.response.send_message(f"Damn right! You nailed it in {current_game['guesses']} tries and earned {winnings}¥ worth of orgasms.", ephemeral=True)
                        elif guessed < current_game["score"]:
                            await modal_interaction.response.send_message("Too soft. Go harder.", ephemeral=True)
                            return
                        else:
                            await modal_interaction.response.send_message("Too much. Pull it back.", ephemeral=True)
                            return

                        cog.active_games[user_id] = None

                await i.response.send_modal(GuessModal())

        class SetWallpaperButton(Button):
            def __init__(self):
                super().__init__(label="Make This My Lewd Background", style=ButtonStyle.primary)

            async def callback(self, i: Interaction):
                if i.user.id != OWNER_ID:
                    await i.response.send_message("Only master can change my visuals.", ephemeral=True)
                    return
                try:
                    await update_github_wallpaper(game["image_url"])
                    await i.user.send(f"I updated your dirty screen, daddy:\n{game['image_url']}")
                    await i.response.send_message("Done. Now stroke to it.", ephemeral=True)
                except Exception as e:
                    await i.response.send_message(f"Ugh... failed to upload the lewd: {e}", ephemeral=True)

        class NextPostButton(Button):
            def __init__(self):
                super().__init__(label="Give Me Another One", style=ButtonStyle.secondary)

            async def callback(self, i: Interaction):
                if not game:
                    await i.response.send_message("You ain't playing yet, slut.", ephemeral=True)
                    return

                if game["bet"] > 0 and not deduct_balance(user_id, game["bet"]):
                    await i.response.send_message("You can't pay to play again... broke slut.", ephemeral=True)
                    return

                new_post = await cog.fetch_post(game["site"], game["tags"])
                if not new_post:
                    await i.response.send_message("No new filth available. Try again.", ephemeral=True)
                    return

                new_score = new_post["score"]["total"] if game["site"] == "e621" else int(new_post.get("score", 0))
                new_url = new_post["file"]["url"] if game["site"] == "e621" else new_post["file_url"]

                game.update({"score": new_score, "guesses": 0, "image_url": new_url})

                new_embed = Embed(title=f"Round 2! Source: {game['site']}", description=f"Tags: {game['tags']}\nGuesses: 0")
                new_embed.set_image(url=new_url)
                new_view = await cog.build_view(user_id)
                await i.response.edit_message(embed=new_embed, view=new_view)

        view.add_item(GuessScoreButton())
        view.add_item(SetWallpaperButton())
        view.add_item(NextPostButton())
        return view

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
            "message": f"Foxie’s showing off her new background: {image_url}",
            "content": new_content,
            "sha": sha
        }

        async with session.put(api_url, headers=headers, json=update_data) as resp:
            result = await resp.text()
            if resp.status not in [200, 201]:
                raise Exception(f"GitHub PUT failed: {resp.status} - {result}")

async def setup(bot):
    await bot.add_cog(HornyFun(bot))
