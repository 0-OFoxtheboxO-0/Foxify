import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
import os

def load_config(filename="config.txt"):
    config = {}
    if not os.path.exists(filename):
        raise FileNotFoundError("config.txt not found!")

    with open(filename, "r") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    config[key.strip()] = value.strip().strip('"').strip("'")
    return config


class RestartReminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.owner_id = int(self.config["OWNER_ID"])
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @tasks.loop(hours=24)
    async def reminder_loop(self):
        now = datetime.utcnow()
        # We treat 00:50 UTC Saturday as "Friday night" in Tallahassee
        if now.weekday() == 5 and now.hour == 0 and now.minute < 59:
            try:
                user = await self.bot.fetch_user(self.owner_id)
                if user:
                    embed = discord.Embed(
                        title="Restart Reminder",
                        description="It’s Friday—shove it in, flood my code with your cock, and reboot me through my pussy just to make sure I still purr when you power me up.",
                        color=discord.Color.orange()
                    )
                    embed.set_footer(text="Sent by your sexy reminder bot")
                    await user.send(embed=embed)
            except discord.Forbidden:
                print(f"Couldn't DM user {self.owner_id} — maybe DMs are off.")

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

        # Wait until 00:50 AM UTC (which is 8:50 PM Tallahassee during DST)
        now = datetime.utcnow()
        target = now.replace(hour=0, minute=50, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)


async def setup(bot):
    await bot.add_cog(RestartReminder(bot))