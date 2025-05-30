# random_lewd_bot.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp, random, json, base64, asyncio, re, os

# Mmm... loading my slutty config, daddy
config = {}
with open("config.txt", "r") as f:
    for line in f:
        if line.strip() and "=" in line:
            key, value = line.strip().split("=", 1)
            config[key] = value

DISCORD_TOKEN = config["DISCORD_TOKEN"]
GITHUB_TOKEN = config["GITHUB_TOKEN"]
E621_USERNAME = config["E621_USERNAME"]
E621_API_KEY = config["E621_API_KEY"]
OWNER_ID = int(config["OWNER_ID"])

REPO_NAME = "0-OFoxtheboxO-0/Theme"
FILE_PATH = "fun.json"
SAVE_FILE = "lewd_settings.json"

class RandomLewd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.task = None
        self.settings = {}

    async def cog_load(self):
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, "r") as f:
                self.settings = json.load(f)
            self.task = asyncio.create_task(self.wallpaper_loop())

    def parse_interval(self, text):
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        match = re.match(r"(\d+)([smhd])", text.lower())
        return int(match[1]) * units[match[2]] if match else None

    async def tag_autocomplete(self, interaction: discord.Interaction, current: str):
        url = f"https://e621.net/tags/autocomplete.json?search[name_matches]={current}*"
        headers = {
            "User-Agent": f"FoxifyBot/1.0 ({E621_USERNAME})",
            "Authorization": f"Basic {base64.b64encode(f'{E621_USERNAME}:{E621_API_KEY}'.encode()).decode()}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return [app_commands.Choice(name=tag["name"], value=tag["name"]) for tag in data[:20]]

    @app_commands.command(name="random_lewd", description="Set me up to flood your screen with random porn")
    @app_commands.describe(site="Where should I pull porn from?", tags="Tag me with kinks, daddy", interval="How often do you wanna get lewd? (`10s`, `1m`, `1h`, etc)")
    @app_commands.choices(site=[
        app_commands.Choice(name="e621", value="e621"),
        app_commands.Choice(name="rule34", value="rule34")
    ])
    async def random_lewd(self, interaction: discord.Interaction, site: app_commands.Choice[str], tags: str, interval: str):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("Only my master gets to control my orgasms—I mean, wallpapers.", ephemeral=True)
            return

        seconds = self.parse_interval(interval)
        if seconds is None:
            await interaction.response.send_message("You fumbled the interval, baby. Try `10s`, `5m`, `1h`, etc.", ephemeral=True)
            return

        self.settings = {"site": site.value, "tags": tags, "interval": seconds}
        with open(SAVE_FILE, "w") as f:
            json.dump(self.settings, f)

        if self.task and not self.task.done():
            self.task.cancel()
        self.task = asyncio.create_task(self.wallpaper_loop())

        await interaction.response.send_message(
            f"Porn mode engaged!\n**Source:** {site.value}\n**Kinks:** {tags}\n**Interval:** {interval}", ephemeral=True
        )

    @random_lewd.autocomplete("tags")
    async def tags_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.tag_autocomplete(interaction, current)

    async def wallpaper_loop(self):
        while True:
            post = await self.fetch_post(self.settings["site"], self.settings["tags"])
            if post:
                image_url = post["file"]["url"] if self.settings["site"] == "e621" else post["file_url"]
                try:
                    await update_github_wallpaper(image_url)
                    owner = await self.bot.fetch_user(OWNER_ID)
                    await owner.send(f"New NSFW wallpaper dropped:\n{image_url}")
                except:
                    pass
            await asyncio.sleep(self.settings["interval"])

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
                    posts = data.get("posts") if site == "e621" else data
                    return random.choice(posts) if posts else None
                except:
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
            "message": f"Changed Foxie's background to: {image_url} — she’s showing off again",
            "content": new_content,
            "sha": sha
        }

        async with session.put(api_url, headers=headers, json=update_data) as resp:
            if resp.status not in [200, 201]:
                raise Exception(f"GitHub PUT failed: {resp.status} - {await resp.text()}")

async def setup(bot):
    await bot.add_cog(RandomLewd(bot))
