import json
import random
import os
import aiohttp
from discord.ext import commands
from discord import app_commands, Interaction, Embed, ButtonStyle
from discord.ui import View, Button

# Load user data
for filename in ["currency.json", "inventory.json", "cards.json"]:
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump({}, f)

def load_json(file):
    with open(file) as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

currency = load_json("currency.json")
inventory = load_json("inventory.json")
cards = load_json("cards.json")

CASE_TYPES = {
    "basic": {
        "cost": 1000,
        "tags": ["solo", "yuri"],
        "rarities": [
            {"name": "Common", "chance": 55, "color": 0x95a5a6},
            {"name": "Uncommon", "chance": 25, "color": 0x2ecc71},
            {"name": "Rare", "chance": 15, "color": 0x3498db},
            {"name": "Epic", "chance": 4, "color": 0x9b59b6},
            {"name": "Legendary", "chance": 1, "color": 0xe67e22},
        ],
    },
    "beast": {
        "cost": 3000,
        "tags": ["furry", "female"],
        "rarities": [
            {"name": "Common", "chance": 40, "color": 0x95a5a6},
            {"name": "Uncommon", "chance": 30, "color": 0x2ecc71},
            {"name": "Rare", "chance": 20, "color": 0x3498db},
            {"name": "Epic", "chance": 8, "color": 0x9b59b6},
            {"name": "Legendary", "chance": 2, "color": 0xe67e22},
        ],
    },
    "extreme": {
        "cost": 600000,
        "tags": ["anal", "bondage"],
        "rarities": [
            {"name": "Common", "chance": 25, "color": 0x95a5a6},
            {"name": "Uncommon", "chance": 30, "color": 0x2ecc71},
            {"name": "Rare", "chance": 25, "color": 0x3498db},
            {"name": "Epic", "chance": 15, "color": 0x9b59b6},
            {"name": "Legendary", "chance": 5, "color": 0xe67e22},
        ],
    },
    "honkai": {
        "cost": 69000,
        "tags": ["honkai:_star_rail"],
        "rarities": [
            {"name": "Common", "chance": 50, "color": 0x95a5a6},
            {"name": "Uncommon", "chance": 25, "color": 0x2ecc71},
            {"name": "Rare", "chance": 15, "color": 0x3498db},
            {"name": "Epic", "chance": 8, "color": 0x9b59b6},
            {"name": "Legendary", "chance": 2, "color": 0xe67e22},
        ],
    },
    "cub": {
        "cost": 999000,
        "tags": ["cub"],
        "rarities": [
            {"name": "Common", "chance": 20, "color": 0x95a5a6},
            {"name": "Uncommon", "chance": 25, "color": 0x2ecc71},
            {"name": "Rare", "chance": 30, "color": 0x3498db},
            {"name": "Epic", "chance": 15, "color": 0x9b59b6},
            {"name": "Legendary", "chance": 10, "color": 0xe67e22},
        ],
    },
}

RARITY_MULTIPLIERS = {
    "Common": 0.75,
    "Uncommon": 0.95,
    "Rare": 1.3,
    "Epic": 2.0,
    "Legendary": 5.0,
}

API_URL = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1"

def save_all():
    save_json("currency.json", currency)
    save_json("inventory.json", inventory)
    save_json("cards.json", cards)

def roll_rarity(case_type):
    rarities = CASE_TYPES[case_type]["rarities"]
    roll = random.randint(1, 100)
    cumulative = 0
    for rarity in rarities:
        cumulative += rarity["chance"]
        if roll <= cumulative:
            return rarity
    return rarities[0]

async def get_image(tags):
    query = "+".join(tags)
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}&tags={query}&limit=100") as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if not data:
                return None
            return random.choice(data).get("file_url")

class DankCase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shop", description="View and buy items from the shop")
    async def shop(self, interaction: Interaction):
        embed = Embed(title="Case Shop", description="Select a case to buy:", color=0x00ff00)
        view = View()

        for case_type, info in CASE_TYPES.items():
            button = Button(label=f"Buy {case_type.capitalize()} Case - {info['cost']} coins", style=ButtonStyle.primary)

            async def callback(interact: Interaction, c=case_type):
                user_id = str(interact.user.id)
                if currency.get(user_id, 0) < CASE_TYPES[c]["cost"]:
                    await interact.response.send_message("Not enough coins!", ephemeral=False)
                    return
                currency[user_id] -= CASE_TYPES[c]["cost"]
                inventory.setdefault(user_id, []).append({"case": c})
                save_all()
                await interact.response.send_message(f"Bought a {c.capitalize()} Case! Use /use to open it.", ephemeral=False)

            button.callback = callback
            view.add_item(button)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory_check(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        items = inventory.get(user_id, [])

        if not items:
            await interaction.response.send_message("Your inventory is empty!", ephemeral=False)
            return

        pages = [items[i:i + 5] for i in range(0, len(items), 5)]
        page = 0

        def make_embed(page_index):
            embed = Embed(title=f"{interaction.user.name}'s Inventory", description=f"Page {page_index + 1}/{len(pages)}", color=0x00ffcc)
            for idx, item in enumerate(pages[page_index], 1):
                if 'name' in item:
                    embed.add_field(name=f"{idx}. {item['name']}", value=f"Rarity: {item['rarity']} | Value: {item['value']} coins", inline=False)
                else:
                    embed.add_field(name=f"{idx}. {item['case'].capitalize()} Case", value="Unopened", inline=False)
            return embed

        async def button_callback(interact: Interaction):
            nonlocal page
            if interact.data['custom_id'] == "prev" and page > 0:
                page -= 1
            elif interact.data['custom_id'] == "next" and page < len(pages) - 1:
                page += 1
            await interact.response.edit_message(embed=make_embed(page), view=view)

        view = View()
        prev_btn = Button(label="Previous", style=ButtonStyle.secondary, custom_id="prev")
        next_btn = Button(label="Next", style=ButtonStyle.secondary, custom_id="next")
        prev_btn.callback = button_callback
        next_btn.callback = button_callback
        view.add_item(prev_btn)
        view.add_item(next_btn)

        await interaction.response.send_message(embed=make_embed(page), view=view, ephemeral=False)

    @app_commands.command(name="cards", description="View your collected cards")
    async def cards_check(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        user_cards = cards.get(user_id, [])

        if not user_cards:
            await interaction.response.send_message("You have no cards!", ephemeral=False)
            return

        pages = [user_cards[i:i + 1] for i in range(len(user_cards))]
        page = 0

        def make_embed(card):
            embed = Embed(title=card['name'], description=f"Rarity: **{card['rarity']}**\nValue: **{card['value']} coins**\nFrom: **{card['source_case'].capitalize()} Case**", color=0xf1c40f)
            embed.set_image(url=card['image'])
            return embed

        async def button_callback(interact: Interaction):
            nonlocal page
            if interact.data['custom_id'] == "prev_card" and page > 0:
                page -= 1
            elif interact.data['custom_id'] == "next_card" and page < len(pages) - 1:
                page += 1
            await interact.response.edit_message(embed=make_embed(pages[page][0]), view=view)

        async def sell_card_callback(interact: Interaction):
            nonlocal page
            card = user_cards.pop(page)
            currency[user_id] = currency.get(user_id, 0) + card['value']
            cards[user_id] = user_cards
            save_all()
            if user_cards:
                page = min(page, len(user_cards) - 1)
                await interact.response.edit_message(content=f"Sold {card['name']} for {card['value']} coins.", embed=make_embed(user_cards[page]), view=view)
            else:
                await interact.response.edit_message(content=f"Sold {card['name']} for {card['value']} coins. You have no more cards.", embed=None, view=None)

        view = View()
        prev_btn = Button(label="Previous", style=ButtonStyle.secondary, custom_id="prev_card")
        next_btn = Button(label="Next", style=ButtonStyle.secondary, custom_id="next_card")
        sell_btn = Button(label="Sell", style=ButtonStyle.danger, custom_id="sell_card")
        prev_btn.callback = button_callback
        next_btn.callback = button_callback
        sell_btn.callback = sell_card_callback
        view.add_item(prev_btn)
        view.add_item(next_btn)
        view.add_item(sell_btn)

        await interaction.response.send_message(embed=make_embed(pages[page][0]), view=view, ephemeral=False)

    @app_commands.command(name="use", description="Use an item or open a case")
    @app_commands.describe(index="Item number to use from inventory")
    async def use(self, interaction: Interaction, index: int):
        user_id = str(interaction.user.id)
        items = inventory.get(user_id, [])

        if index < 1 or index > len(items):
            await interaction.response.send_message("Invalid index.", ephemeral=False)
            return

        item = items.pop(index - 1)
        if 'case' in item:
            case_type = item['case']
            case = CASE_TYPES[case_type]
            rarity = roll_rarity(case_type)
            image_url = await get_image(case['tags'])

            if not image_url:
                await interaction.response.send_message("Failed to get image.", ephemeral=False)
                return

            base_value = case['cost']
            multiplier = RARITY_MULTIPLIERS.get(rarity['name'], 1)
            value = int(base_value * multiplier)

            reward = {
                "name": f"{rarity['name']} {case_type.capitalize()} Card",
                "rarity": rarity['name'],
                "value": value,
                "image": image_url,
                "source_case": case_type
            }
            inventory[user_id] = items
            cards.setdefault(user_id, []).append(reward)
            save_all()

            embed = Embed(title=f"{interaction.user.name} opened a {case_type.capitalize()} Case!",
                          description=f"**{reward['name']}**\nRarity: **{reward['rarity']}**\nValue: **{reward['value']} coins**",
                          color=rarity['color'])
            embed.set_image(url=image_url)
            embed.set_footer(text="Use /cards to check your rewards!")

            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("This item can't be used yet.", ephemeral=False)

    @app_commands.command(name="sell", description="Sell an item from your inventory")
    @app_commands.describe(index="Item number to sell")
    async def sell(self, interaction: Interaction, index: int):
        user_id = str(interaction.user.id)
        items = inventory.get(user_id, [])

        if index < 1 or index > len(items):
            await interaction.response.send_message("Invalid index.", ephemeral=False)
            return

        item = items.pop(index - 1)
        if 'value' in item:
            currency[user_id] = currency.get(user_id, 0) + item['value']
            inventory[user_id] = items
            save_all()
            await interaction.response.send_message(f"Sold {item['name']} for {item['value']} coins.", ephemeral=False)
        else:
            await interaction.response.send_message("You can't sell this item.", ephemeral=False)

async def setup(bot):
    await bot.add_cog(DankCase(bot))

