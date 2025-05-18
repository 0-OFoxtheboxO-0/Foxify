import discord  # Discord API wrapper
import requests  # For making HTTP requests
import base64  # Encoding/decoding GitHub file content
import json  # Reading/writing config or data files
import os  # File path operations
import atexit  # Register function to run on exit
import traceback  # Captures detailed exception info
import random
import xml.etree.ElementTree as ET
import time

from discord.ext import commands, tasks  # Bot commands and background tasks
from discord import app_commands, ButtonStyle  # For slash commands and buttons
from discord.ui import View, Button, Select  # For interactive buttons and dropdowns
from datetime import datetime, timedelta
from pytz import timezone  # For timezone-aware times
from urllib.parse import urlparse  # Not currently used

# ==== Configuration Constants ====
OWNER_ID = 700795007950651422  # Your Discord user ID for owner-only commands
SUB_FILE = "subscribed_users.json"  # Stores user IDs subscribed to updates
HEARTBEAT_FILE = "heartbeat.json"  # Tracks when bot last ran
REPO_OWNER = "0-OFoxtheboxO-0"
REPO_NAME = "Theme"
FILE_PATH = "fun.json"  # GitHub path to the file you're editing

# ==== Currency System Constants ====
CURRENCY_FILE = "currency.json"  # Stores user currency balances
INVENTORY_FILE = "inventory.json"  # Stores user inventories
SHOP_FILE = "shop.json"  # Stores shop items

# Default shop items
DEFAULT_SHOP_ITEMS = [
    {"id": "premium_wallpaper", "name": "Premium Wallpaper", "description": "Unlock exclusive wallpapers", "price": 500, "type": "unlock"},
    {"id": "daily_boost", "name": "Daily Boost", "description": "Doubles your daily rewards for 3 days", "price": 750, "type": "boost", "duration": 3},
    {"id": "custom_tag", "name": "Custom Tag", "description": "Add a custom tag to your profile", "price": 300, "type": "profile"},
    {"id": "background_change", "name": "Background Change", "description": "Change the site background immediately", "price": 1000, "type": "action"},
    {"id": "rare_avatar", "name": "Rare Avatar", "description": "Exclusive avatar for your profile", "price": 2000, "type": "cosmetic"}
]

# Daily currency reward amount
DAILY_REWARD = 100
# Currency for adding a new wallpaper
WALLPAPER_REWARD = 50

# ==== Load Tokens from config.txt ====
def load_tokens(file="config.txt"):
    path = os.path.join(os.path.dirname(file), file)
    tokens = {}
    with open(path) as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                tokens[k] = v
    return tokens

tokens = load_tokens()
DISCORD_TOKEN = tokens.get("DISCORD_TOKEN", "")
GITHUB_TOKEN = tokens.get("GITHUB_TOKEN", "")
E621_USERNAME = tokens.get("E621_USERNAME", "")
E621_API_KEY = tokens.get("E621_API_KEY", "")

if not DISCORD_TOKEN:
    print("BRUH no Discord token?! Check your config.txt file!")
    exit(1)

# ==== Initialize Bot ====
intents = discord.Intents.default()
intents.message_content = True  # Needed for message-based commands
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree  # Slash command tree

# ==== File Management Helpers ====
def load_users():
    return json.load(open(SUB_FILE)) if os.path.exists(SUB_FILE) else []

def save_users(data):
    json.dump(data, open(SUB_FILE, "w"))

def write_heartbeat():
    json.dump({"last_heartbeat": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}, open(HEARTBEAT_FILE, "w"))

def read_heartbeat():
    if not os.path.exists(HEARTBEAT_FILE):
        return "idk when lol"
    return json.load(open(HEARTBEAT_FILE)).get("last_heartbeat", "idk when lol")

def est_time():
    return datetime.now(timezone("America/New_York")).strftime('%Y-%m-%d %I:%M %p %Z')

# ==== Currency System Functions ====
def load_currency():
    return json.load(open(CURRENCY_FILE)) if os.path.exists(CURRENCY_FILE) else {}

def save_currency(data):
    json.dump(data, open(CURRENCY_FILE, "w"))

def load_inventory():
    return json.load(open(INVENTORY_FILE)) if os.path.exists(INVENTORY_FILE) else {}

def save_inventory(data):
    json.dump(data, open(INVENTORY_FILE, "w"))

def load_shop():
    if os.path.exists(SHOP_FILE):
        return json.load(open(SHOP_FILE))
    else:
        # Initialize with default items
        json.dump(DEFAULT_SHOP_ITEMS, open(SHOP_FILE, "w"))
        return DEFAULT_SHOP_ITEMS

def save_shop(data):
    json.dump(data, open(SHOP_FILE, "w"))

def get_user_currency(user_id):
    """Get a user's currency balance"""
    currency_data = load_currency()
    user_id_str = str(user_id)
    
    if user_id_str not in currency_data:
        currency_data[user_id_str] = {
            "balance": 0,
            "last_daily": "",
            "boosts": {}
        }
        save_currency(currency_data)
        
    return currency_data[user_id_str]

def add_currency(user_id, amount):
    """Add currency to a user's balance"""
    currency_data = load_currency()
    user_id_str = str(user_id)
    
    if user_id_str not in currency_data:
        currency_data[user_id_str] = {
            "balance": 0,
            "last_daily": "",
            "boosts": {}
        }
    
    currency_data[user_id_str]["balance"] += amount
    save_currency(currency_data)
    return currency_data[user_id_str]["balance"]

def has_daily_boost(user_id):
    """Check if user has an active daily boost"""
    user_data = get_user_currency(user_id)
    if "boosts" not in user_data:
        user_data["boosts"] = {}
        
    if "daily_boost" not in user_data["boosts"]:
        return False
        
    boost_expiry = datetime.fromisoformat(user_data["boosts"]["daily_boost"])
    return datetime.now() < boost_expiry

def get_user_inventory(user_id):
    """Get a user's inventory"""
    inventory_data = load_inventory()
    user_id_str = str(user_id)
    
    if user_id_str not in inventory_data:
        inventory_data[user_id_str] = []
        save_inventory(inventory_data)
        
    return inventory_data[user_id_str]

def add_to_inventory(user_id, item_id):
    """Add an item to a user's inventory"""
    inventory_data = load_inventory()
    user_id_str = str(user_id)
    
    if user_id_str not in inventory_data:
        inventory_data[user_id_str] = []
    
    # Get the item from the shop
    shop_items = load_shop()
    item = next((item for item in shop_items if item["id"] == item_id), None)
    
    if not item:
        return False
    
    # Add item with timestamp
    inventory_data[user_id_str].append({
        "id": item_id,
        "name": item["name"],
        "acquired": datetime.now().isoformat(),
        "used": False
    })
    
    save_inventory(inventory_data)
    return True

users = load_users()
atexit.register(write_heartbeat)  # Write last heartbeat on exit

# Initialize shop on startup if doesn't exist
if not os.path.exists(SHOP_FILE):
    save_shop(DEFAULT_SHOP_ITEMS)

# ==== GitHub Helper Function ====
async def update_github_background(image_url, source_name):
    """Update GitHub fun.json with a new background URL"""
    gh_headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    gh_api = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    gh_get = requests.get(gh_api, headers=gh_headers)
    gh_get.raise_for_status()
    data = gh_get.json()
    sha = data["sha"]
    content = base64.b64decode(data["content"]).decode()
    json_data = json.loads(content)
    json_data["background"]["url"] = image_url
    encoded = base64.b64encode(json.dumps(json_data, indent=2).encode()).decode()
    payload = {"message": f"Updated {source_name} wallpaper to {image_url}", "content": encoded, "sha": sha}
    put = requests.put(gh_api, headers=gh_headers, json=payload)
    put.raise_for_status()
    return True

# ==== Button View Classes ====
class ImageSelectionView(View):
    def __init__(self, original_interaction, image_url, tags, source_type, timeout=60):
        super().__init__(timeout=timeout)
        self.original_interaction = original_interaction
        self.image_url = image_url
        self.tags = tags
        self.source_type = source_type  # "e621" or "rule34"
        
        # Add buttons
        self.add_item(Button(style=ButtonStyle.green, label="Slay", custom_id="accept"))
        self.add_item(Button(style=ButtonStyle.blurple, label="Next vibe", custom_id="retry"))
        self.add_item(Button(style=ButtonStyle.red, label="Nah fam", custom_id="cancel"))
    
    async def interaction_check(self, interaction):
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message("This ain't your pic bestie!", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        # Edit the message when the view times out
        try:
            await self.original_interaction.edit_original_response(
                embed=discord.Embed(
                    title="Time's up frfr",
                    description="You took way too long to respond. Command canceled, no cap.",
                    color=discord.Color.dark_gray()
                ),
                view=None
            )
        except:
            pass

class ShopView(View):
    def __init__(self, original_interaction, timeout=60):
        super().__init__(timeout=timeout)
        self.original_interaction = original_interaction
        
        # Add dropdown for shop items
        shop_items = load_shop()
        options = [
            discord.SelectOption(
                label=item["name"],
                description=f"{item['description']} - {item['price']} coins",
                value=item["id"]
            ) for item in shop_items
        ]
        
        self.add_item(ShopSelect(options))
    
    async def interaction_check(self, interaction):
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message("This shop ain't for you bestie!", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        try:
            await self.original_interaction.edit_original_response(
                embed=discord.Embed(
                    title="Shop closed",
                    description="The shop timed out. Come back later!",
                    color=discord.Color.dark_gray()
                ),
                view=None
            )
        except:
            pass

class ShopSelect(Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Choose an item to purchase...",
            options=options,
            custom_id="shop_select"
        )
    
    async def callback(self, interaction):
        item_id = self.values[0]
        shop_items = load_shop()
        item = next((item for item in shop_items if item["id"] == item_id), None)
        
        if not item:
            await interaction.response.send_message("Item not found in shop. That's sus.", ephemeral=True)
            return
            
        # Get user balance
        user_currency = get_user_currency(interaction.user.id)
        
        if user_currency["balance"] < item["price"]:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Not enough coins",
                    description=f"You need {item['price']} coins but only have {user_currency['balance']}. Go get that bag!",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
            
        # Process purchase based on item type
        if item["type"] == "boost" and item["id"] == "daily_boost":
            # Apply daily boost
            currency_data = load_currency()
            user_id_str = str(interaction.user.id)
            
            if "boosts" not in currency_data[user_id_str]:
                currency_data[user_id_str]["boosts"] = {}
                
            # Set expiry date
            boost_expiry = datetime.now() + timedelta(days=item["duration"])
            currency_data[user_id_str]["boosts"]["daily_boost"] = boost_expiry.isoformat()
            
            # Deduct coins
            currency_data[user_id_str]["balance"] -= item["price"]
            save_currency(currency_data)
            
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Boost Activated!",
                    description=f"Daily boost active for {item['duration']} days! Your daily rewards are doubled!",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
            
        elif item["type"] == "action" and item["id"] == "background_change":
            # Deduct coins first
            user_id_str = str(interaction.user.id)
            currency_data = load_currency()
            currency_data[user_id_str]["balance"] -= item["price"]
            save_currency(currency_data)
            
            # Let user choose a background
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Background Change",
                    description="Drop a direct image URL or upload an image to change the background.",
                    color=discord.Color.blue()
                ),
                ephemeral=True
            )
            
            # Wait for user's response with the image
            def check(msg):
                return msg.author.id == interaction.user.id and (
                    msg.attachments or 
                    any(ext in msg.content.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif'])
                )
                
            try:
                msg = await bot.wait_for('message', timeout=60.0, check=check)
                image_url = msg.attachments[0].url if msg.attachments else msg.content
                
                # Update background
                await update_github_background(image_url, "shop purchase")
                
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Background Updated!",
                        description="Your new background is live! Major flex!",
                        color=discord.Color.green()
                    ),
                    ephemeral=True
                )
            except asyncio.TimeoutError:
                # Refund if they didn't provide an image
                currency_data = load_currency()
                currency_data[user_id_str]["balance"] += item["price"]
                save_currency(currency_data)
                
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Timeout - Coins Refunded",
                        description="You didn't provide an image in time. Your coins have been refunded.",
                        color=discord.Color.orange()
                    ),
                    ephemeral=True
                )
        else:
            # For other item types, just add to inventory and deduct coins
            success = add_to_inventory(interaction.user.id, item_id)
            
            if success:
                # Deduct coins
                currency_data = load_currency()
                user_id_str = str(interaction.user.id)
                currency_data[user_id_str]["balance"] -= item["price"]
                save_currency(currency_data)
                
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Item Purchased!",
                        description=f"You got the {item['name']}! Check your inventory with /inventory.",
                        color=discord.Color.green()
                    ),
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Purchase Failed",
                        description="Couldn't add item to inventory. That's an L.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )

# ==== Error Notification ====
async def notify_error(text):
    for uid in users:
        try:
            user = await bot.fetch_user(uid)
            await user.send(embed=discord.Embed(title="Bot crashed fr", description=text, color=discord.Color.red()))
        except:
            pass

# ==== Bot Ready Event ====
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user} and we vibin'.")
    try:
        last = datetime.strptime(read_heartbeat(), '%Y-%m-%d %H:%M:%S').replace(
            tzinfo=timezone("UTC")).astimezone(timezone("America/New_York")).strftime('%Y-%m-%d %I:%M %p %Z')
    except:
        last = read_heartbeat()
    for uid in users:
        try:
            user = await bot.fetch_user(uid)
            await user.send(embed=discord.Embed(title="I'm up!", description=f"I was catching Zs at {last}. I'm back in the chat — hit the site to keep me alive fr.", color=discord.Color.blurple()))
        except:
            pass
    if not send_bot_info.is_running():
        send_bot_info.start()
    if not heartbeat.is_running():
        heartbeat.start()

# ==== Error Handlers ====
@bot.event
async def on_command_error(ctx, error):
    await notify_error(f"Command error: {type(error).__name__} - {error}")

@tree.error
async def on_app_command_error(interaction, error):
    await notify_error(f"Slash command error: {type(error).__name__} - {error}")
    try:
        await interaction.followup.send(embed=discord.Embed(title="Bruh", description="Something's not bussin'. We got issues.", color=discord.Color.red()), ephemeral=True)
    except:
        pass

# ==== Button Interaction Handler ====
@bot.event
async def on_interaction(interaction):
    # Handle button interactions
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        
        if custom_id == "accept":
            try:
                # Extract info from the message embed to get image URL
                embed = interaction.message.embeds[0]
                image_url = embed.image.url
                source_type = "e621" if "e621" in embed.title.lower() else "rule34"
                
                await interaction.response.defer(ephemeral=True)
                
                # Update GitHub with the selected image
                await update_github_background(image_url, source_type)
                
                # Add wallpaper reward to user who submitted it
                new_balance = add_currency(interaction.user.id, WALLPAPER_REWARD)
                
                # Update the original message
                success_embed = discord.Embed(
                    title=f"{source_type.capitalize()} Pic - Major W!",
                    description=f"Background image updated, no cap! You earned {WALLPAPER_REWARD} coins. New balance: {new_balance} coins.",
                    color=discord.Color.green()
                )
                success_embed.set_image(url=image_url)
                await interaction.edit_original_response(embed=success_embed, view=None)
                
            except Exception as e:
                await notify_error(traceback.format_exc())
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="That's an L",
                        description=f"GitHub update flopped: {str(e)}",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                
        elif custom_id == "retry":
            # Extract current tags and source from the message embed
            embed = interaction.message.embeds[0]
            source_type = "e621" if "e621" in embed.title.lower() else "rule34"
            
            # Extract tags correctly from the description
            description = embed.description
            tags = ""
            if "Tags: " in description:
                tags_section = description.split("Tags: ", 1)[1]
                # Get tags before the newline
                tags = tags_section.split("\n")[0].strip()
            
            await interaction.response.defer(ephemeral=True)
            
            # Call the appropriate function to get a new image
            if source_type == "e621":
                await process_e621_search(interaction, tags)
            else:  # rule34
                await process_rule34_search(interaction, tags)
                
        elif custom_id == "cancel":
            # Cancel the operation
            await interaction.response.defer(ephemeral=True)
            cancel_embed = discord.Embed(
                title="We out",
                description="Image selection? Canceled. We good.",
                color=discord.Color.dark_gray()
            )
            await interaction.edit_original_response(embed=cancel_embed, view=None)
    
    # Don't block other interactions
    if not interaction.response.is_done():
        try:
            await bot.process_application_commands(interaction)
        except:
            pass

# ==== API Search Functions ====
async def process_e621_search(interaction, tags):
    """Process e621 search and display results with buttons"""
    query = "+".join(tags.split())
    api_url = f"https://e621.net/posts.json?tags={query}+order:random&limit=5"
    
    headers = {
        "User-Agent": f"DiscordBot/1.0 (by {E621_USERNAME} on e621)"
    }
    auth = (E621_USERNAME, E621_API_KEY)

    try:
        res = requests.get(api_url, headers=headers, auth=auth)
        res.raise_for_status()
        posts = res.json().get("posts", [])

        valid_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webm")
        image_url = None

        for post in posts:
            file_url = post.get("file", {}).get("url")
            if file_url and file_url.lower().endswith(valid_extensions):
                image_url = file_url
                break

        if not image_url:
            embed = discord.Embed(
                title="No valid pic found",
                description="Found some posts but none with usable pics/gifs. Big yikes.",
                color=discord.Color.orange()
            )
            if isinstance(interaction, discord.Interaction) and not interaction.response.is_done():
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.followup.send(embed=embed)
            return

        # Create embed with image
        embed = discord.Embed(
            title="e621 Pic Check",
            description=f"Tags: {tags}\n\nHit Slay to use this pic, Next vibe for something else, or Nah fam to dip.",
            color=discord.Color.teal()
        )
        embed.set_image(url=image_url)
        
        # Create view with buttons
        view = ImageSelectionView(interaction, image_url, tags, "e621")
        
        # Send or edit message based on interaction state
        if isinstance(interaction, discord.Interaction) and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.edit_original_response(embed=embed, view=view)

    except Exception as e:
        await notify_error(traceback.format_exc())
        
        error_embed = discord.Embed(
            title="Down bad rn",
            description=f"Something's broken with e621: {str(e)}",
            color=discord.Color.red()
        )
        
        if isinstance(interaction, discord.Interaction) and not interaction.response.is_done():
            await interaction.response.send_message(embed=error_embed)
        else:
            await interaction.followup.send(embed=error_embed)

async def process_rule34_search(interaction, tags):
    """Process Rule34 search and display results with buttons"""
    query = "+".join(tags.split())
    api_url = f"https://rule34.xxx/index.php?page=dapi&s=post&q=index&tags={query}+sort:random&limit=100"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        res = requests.get(api_url, headers=headers)
        res.raise_for_status()
        
        # Check if we got XML content before parsing
        if not res.content or not res.content.strip():
            embed = discord.Embed(
                title="Empty feed fr",
                description="The API sent back nothing. Try different tags no cap.",
                color=discord.Color.orange()
            )
            if isinstance(interaction, discord.Interaction) and not interaction.response.is_done():
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.followup.send(embed=embed)
            return
        
        try:
            root = ET.fromstring(res.content)
        except ET.ParseError:
            embed = discord.Embed(
                title="Can't parse that",
                description="Couldn't read the API response. Site might be ghosting us.",
                color=discord.Color.red()
            )
            if isinstance(interaction, discord.Interaction) and not interaction.response.is_done():
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.followup.send(embed=embed)
            return

        posts = root.findall("post")
        if not posts:
            embed = discord.Embed(
                title="No results bestie",
                description="Couldn't find anything with those tags. Try something else fr.",
                color=discord.Color.orange()
            )
            if isinstance(interaction, discord.Interaction) and not interaction.response.is_done():
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.followup.send(embed=embed)
            return

        valid_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webm")
        image_url = None

        random.shuffle(posts)
        for post in posts:
            file_url = post.attrib.get("file_url", "")
            if file_url.lower().endswith(valid_extensions):
                image_url = file_url
                break

        if not image_url:
            embed = discord.Embed(
                title="No valid pic",
                description="Found posts but none had usable pics or gifs. That's sus.",
                color=discord.Color.orange()
            )
            if isinstance(interaction, discord.Interaction) and not interaction.response.is_done():
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.followup.send(embed=embed)
            return

        # Create embed with image
        embed = discord.Embed(
            title="Rule34 Pic Check",
            description=f"Tags: {tags}\n\nHit Slay to use this pic, Next vibe for something else, or Nah fam to dip.",
            color=discord.Color.magenta()
        )
        embed.set_image(url=image_url)
        
        # Create view with buttons
        view = ImageSelectionView(interaction, image_url, tags, "rule34")
        
        # Send or edit message based on interaction state
        if isinstance(interaction, discord.Interaction) and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.edit_original_response(embed=embed, view=view)

    except Exception as e:
        await notify_error(traceback.format_exc())
        
        error_embed = discord.Embed(
            title="Major L",
            description=f"Something flopped: {str(e)}",
            color=discord.Color.red()
        )
        
        if isinstance(interaction, discord.Interaction) and not interaction.response.is_done():
            await interaction.response.send_message(embed=error_embed)
        else:
            await interaction.followup.send(embed=error_embed)

# ==== Background Tasks ====
@tasks.loop(hours=24)
async def send_bot_info():
    for uid in users:
        try:
            user = await bot.fetch_user(uid)
            await user.send(embed=discord.Embed(title="Weekly Foxify Update", description="I've been running straight for a week! Don't forget to check on your themes. And collect your daily coins with /daily!", color=discord.Color.gold()))
        except:
            pass

@tasks.loop(minutes=5)
async def heartbeat():
    write_heartbeat()

# ==== Slash Commands ====

# /wall - Updates GitHub fun.json background image manually
@tree.command(name="wall", description="Update the background in fun.json")
@app_commands.describe(image_url="Direct link to an image (optional)")
async def wall(interaction, image_url: str = None, attachment: discord.Attachment = None):
    await interaction.response