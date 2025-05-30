import discord
from discord import app_commands, Interaction
from discord.ext import commands
import random
import json
import os

DATA_FILE = "currency.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

class Currency(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_balance(self, user_id: int) -> int:
        balances = load_data()
        return balances.get(str(user_id), 0)

    def set_balance(self, user_id: int, amount: int):
        balances = load_data()
        balances[str(user_id)] = amount
        save_data(balances)

    def add_balance(self, user_id: int, amount: int):
        balances = load_data()
        balances[str(user_id)] = balances.get(str(user_id), 0) + amount
        save_data(balances)

    @app_commands.command(name="balance", description="Check your current ¥ balance")
    async def balance(self, interaction: Interaction):
        amount = self.get_balance(interaction.user.id)
        await interaction.response.send_message(f"{interaction.user.mention}, you have ¥{amount}.")

    @app_commands.command(name="give", description="Give someone some of your ¥")
    @app_commands.describe(user="User to give money to", amount="How much ¥ to give")
    async def give(self, interaction: Interaction, user: discord.Member, amount: int):
        if user.id == interaction.user.id:
            await interaction.response.send_message("You can't give yourself money!", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("You must give more than 0!", ephemeral=True)
            return
        if self.get_balance(interaction.user.id) < amount:
            await interaction.response.send_message("You don't have enough ¥ to give.", ephemeral=True)
            return

        self.add_balance(interaction.user.id, -amount)
        self.add_balance(user.id, amount)
        await interaction.response.send_message(f"You gave ¥{amount} to {user.mention}.")

    @app_commands.command(name="slut", description="Do nasty sh*t for some dirty ¥")
    async def bang(self, interaction: Interaction):
        amount = random.randint(1, 20)
        messages = [
            f"You spread your legs on cam and moaned their name—they busted hard and tipped ¥{amount}.",
            f"You got throat-f*cked live on stream and some twisted freak dropped ¥{amount} as a thank-you.",
            f"You shoved a toy deep inside, hit record, and watched the simps flood you with ¥{amount}.",
            f"Someone watched you gag and drool on a monster c*ck and sent ¥{amount} with a heart emoji.",
            f"You got spitroasted by two futas and the whole site crashed—still, you got ¥{amount}.",
            f"You begged like a little c*m-hungry brat and some stranger emptied ¥{amount} into your DMs.",
            f"A demon bred you in a public roleplay server, and the viewers tossed ¥{amount} at you in praise.",
            f"You squirted so hard it hit the webcam—one viewer nut instantly and tipped ¥{amount}.",
            f"You let a slime tentacle inside every hole and the comments section exploded—¥{amount} earned.",
            f"You called someone 'master' while grinding on a pillow live—¥{amount} dropped in seconds."
        ]
        self.add_balance(interaction.user.id, amount)
        await interaction.response.send_message(random.choice(messages))

async def setup(bot):
    await bot.add_cog(Currency(bot))