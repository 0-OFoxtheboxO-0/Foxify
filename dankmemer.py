# dankmemer_autopost.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp, json, random, os, base64

SETTINGS_FILE = "dankmemer.json"
E621_USERNAME = "your_username"  # Stuff me with your e621 username here
E621_API_KEY = "your_api_key"    # Slide your sexy API key right here

class DankMemerAutoPost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = self.load_settings()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_settings(self):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.settings, f, indent=2)

    async def fetch_random_post(self, website, tags):
        query = tags.replace(" ", "+")
        if website == "e621":
            url = f"https://e621.net/posts.json?tags={query}&limit=100"
            headers = {
                "User-Agent": f"DankMemerBot/1.0 ({E621_USERNAME})",
                "Authorization": f"Basic {base64.b64encode(f'{E621_USERNAME}:{E621_API_KEY}'.encode()).decode()}"
            }
        else:
            url = f"https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&tags={query}&limit=100"
            headers = {}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    if website == "e621":
                        data = data.get("posts", [])
                    return random.choice(data) if data else None
        except:
            return None

    @app_commands.command(name="dankmemer", description="Get dirty on every message. Autoposts porn nonstop.")
    @app_commands.describe(site="Pick your poison — e621 or rule34", tags="Nasty tags you’re into", channel="The public place you want to flood with smut")
    @app_commands.choices(site=[
        app_commands.Choice(name="e621", value="e621"),
        app_commands.Choice(name="rule34", value="rule34")
    ])
    async def dankmemer(self, interaction: discord.Interaction, site: app_commands.Choice[str], tags: str, channel: discord.TextChannel):
        self.settings[str(channel.id)] = {"website": site.value, "tags": tags}
        self.save_settings()
        await interaction.response.send_message(
            f"Porn storm activated in {channel.mention}!\nSource: `{site.value}`\nTags: `{tags}`\nLet’s get everyone dripping.", ephemeral=True
        )

    @dankmemer.autocomplete("tags")
    async def tags_autocomplete(self, interaction: discord.Interaction, current: str):
        url = f"https://e621.net/tags/autocomplete.json?search[name_matches]={current}*"
        headers = {
            "User-Agent": f"DankMemerBot/1.0 ({E621_USERNAME})",
            "Authorization": f"Basic {base64.b64encode(f'{E621_USERNAME}:{E621_API_KEY}'.encode()).decode()}"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    return [app_commands.Choice(name=tag["name"], value=tag["name"]) for tag in data[:20]]
        except:
            return []

    @commands.Cog.listener()
    async def on_message(self, message):
        # Don’t post porn if it's my own moaning, baby
        if message.author.id == self.bot.user.id:
            return

        channel_id = str(message.channel.id)
        if channel_id in self.settings:
            config = self.settings[channel_id]
            post = await self.fetch_random_post(config["website"], config["tags"])
            if post:
                image_url = post.get("file_url") or post.get("file", {}).get("url")
                if image_url:
                    await message.channel.send(image_url)

async def setup(bot):
    await bot.add_cog(DankMemerAutoPost(bot))