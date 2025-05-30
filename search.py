import aiohttp
import base64
import json
import random
from discord import app_commands, Embed, Interaction, ButtonStyle
from discord.ext import commands
from discord.ui import View, Button

# Slutty config loading — getting all my juicy keys
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

class Spicy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="spicy", description="Slap me with something filthy from e621 or rule34")
    @app_commands.describe(source="Choose where I get my porn", tags="Search tags to make me beg (e.g., 'futa anal')")
    @app_commands.choices(source=[
        app_commands.Choice(name="e621", value="e621"),
        app_commands.Choice(name="rule34", value="rule34"),
    ])
    async def spicy_search(self, interaction: Interaction, source: app_commands.Choice[str], tags: str):
        await interaction.response.defer()

        site = source.value
        post = await self.fetch_post(site, tags)
        if not post:
            await interaction.followup.send("Nothing came up... maybe spank me harder next time.")
            return

        image_url = post["file"]["url"] if site == "e621" else post["file_url"]
        embed = Embed(title=f"Here's a slutty treat from {site}!", description=f"Tags: {tags}")
        embed.set_image(url=image_url)

        view = await self.build_view(site, tags, image_url)
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

    async def build_view(self, site, tags, image_url):
        view = View(timeout=None)
        cog = self

        class SetWallpaperButton(Button):
            def __init__(self):
                super().__init__(label="Set as Foxie's Porny Wallpaper", style=ButtonStyle.primary)

            async def callback(self, i: Interaction):
                if i.user.id != OWNER_ID:
                    await i.response.send_message("Only master gets to set my background, slut.", ephemeral=True)
                    return
                try:
                    await update_github_wallpaper(image_url)
                    await i.user.send(f"Mmm, wallpaper set to this filthy shot: {image_url}")
                    await i.response.send_message("Wallpaper updated. I'm dripping.", ephemeral=True)
                except Exception as e:
                    await i.response.send_message(f"Couldn't stuff it into GitHub: {e}", ephemeral=True)
                    print("GitHub error:", e)

        class NextPostButton(Button):
            def __init__(self):
                super().__init__(label="More porn please", style=ButtonStyle.secondary)

            async def callback(self, i: Interaction):
                new_post = await cog.fetch_post(site, tags)
                if not new_post:
                    await i.response.send_message("That's it, I'm all out of filth... for now.", ephemeral=True)
                    return
                new_url = new_post["file"]["url"] if site == "e621" else new_post["file_url"]
                new_embed = Embed(title=f"More porn from {site}!", description=f"Tags: {tags}")
                new_embed.set_image(url=new_url)
                new_view = await cog.build_view(site, tags, new_url)
                await i.response.edit_message(embed=new_embed, view=new_view)

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
            "message": f"Updated Foxie's lewd background to {image_url}",
            "content": new_content,
            "sha": sha
        }

        async with session.put(api_url, headers=headers, json=update_data) as resp:
            result = await resp.text()
            if resp.status not in [200, 201]:
                raise Exception(f"GitHub PUT failed: {resp.status} - {result}")
            print("GitHub update succeeded. I’m soaking in new visuals:", result)

async def setup(bot):
    await bot.add_cog(Spicy(bot))