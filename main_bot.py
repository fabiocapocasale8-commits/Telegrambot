import discord
from discord.ext import commands
import ctypes
import json
import os
import random
import requests
import asyncio
import string
import time
import datetime
from colorama import Fore
import platform
import itertools
from gtts import gTTS
import io
import qrcode
import pyfiglet

# Import license validation
from src.remote_license_validator import LicenseValidator, get_hardware_id

# Get Discord token from environment (set by Telegram bot)
token = os.getenv('DISCORD_TOKEN')
if not token:
    print("❌ No Discord token provided!")
    exit(1)

print("""
     \x1b[38;5;127m ██▓███\x1b[38;5;255m   ██▓    ▄▄▄        ██████  ███▄ ▄███▓ ▄▄▄      
     \x1b[38;5;127m▓██░  ██\x1b[38;5;255m▒▓██▒   ▒████▄    ▒██    ▒ ▓██▒▀█▀ ██▒▒████▄    
     \x1b[38;5;127m▓██░ ██▓\x1b[38;5;255m▒▒██░   ▒██  ▀█▄  ░ ▓██▄   ▓██    ▓██░▒██  ▀█▄  
     \x1b[38;5;127m▒██▄█▓▒\x1b[38;5;255m ▒▒██░   ░██▄▄▄▄██   ▒   ██▒▒██    ▒██ ░██▄▄▄▄██ 
     \x1b[38;5;127m▒██▒ ░\x1b[38;5;255m  ░░██████▒▓█   ▓██▒▒██████▒▒▒██▒   ░██▒ ▓█   ▓██▒
     \x1b[38;5;127m▒▓▒░ ░\x1b[38;5;255m  ░░ ▒░▓  ░▒▒   ▓▒█░▒ ▒▓▒ ▒ ░░ ▒░   ░  ░ ▒▒   ▓▒█░
     \x1b[38;5;127m░▒ ░\x1b[38;5;255m     ░ ░ ▒  ░ ▒   ▒▒ ░░ ░▒  ░ ░░  ░      ░  ▒   ▒▒ ░
     \x1b[38;5;127m░░\x1b[38;5;255m         ░ ░    ░   ▒   ░  ░  ░  ░      ░     ░   ▒   
     \x1b[38;5;127m             \x1b[38;5;255m░  ░     ░  ░      ░         ░         ░  ░
                                                   \n""")

print("✅ Authentication completed via Telegram bot")
print("🚀 Starting Discord bot...")

y = Fore.LIGHTYELLOW_EX
b = Fore.LIGHTBLUE_EX
w = Fore.LIGHTWHITE_EX

__version__ = "3.2"

start_time = datetime.datetime.now(datetime.timezone.utc)

# Create unique config file based on token hash
import hashlib
token_hash = hashlib.md5(token.encode()).hexdigest()[:8]
config_file_path = f"config/config_{token_hash}.json"

# Create default config if user's config doesn't exist
default_config = {
    "prefix": ".",
    "remote-users": [],
    "autoreply": {
        "messages": [
            "https://github.com/",
            "https://discord.gg/"
        ],
        "channels": [],
        "users": []
    },
    "afk": {
        "enabled": False,
        "message": "I'm currently AFK"
    },
    "copycat": {
        "users": []
    },
    "auto_channels": {},
    "shortcuts": {},
    "flag_word": ""
}

# Load or create user's unique config
if os.path.exists(config_file_path):
    with open(config_file_path, "r") as file:
        config = json.load(file)
else:
    config = default_config.copy()
    os.makedirs("config", exist_ok=True)
    with open(config_file_path, "w") as file:
        json.dump(config, file, indent=4)

prefix = config.get("prefix", ".")
message_generator = itertools.cycle(config["autoreply"]["messages"])

# Track users who already received auto DM reply
auto_dm_replied_users = set()
# Track auto DM messages sent to users for flag deletion
auto_dm_messages = {}
# Enhanced user tracking for anti-ban protection
auto_dm_user_data = {}
# Track delete after time for commands (in seconds, None means never delete)
delete_after_time = None
# Track custom shortcuts
shortcuts = config.get("shortcuts", {})

def save_config(config):
    with open(config_file_path, "w") as file:
        json.dump(config, file, indent=4)

async def monitor_license_expiration():
    """Monitor license expiration and stop bot when expired"""
    license_system = LicenseValidator()
    hardware_id = get_hardware_id()
    
    while True:
        try:
            # Check license every 30 minutes
            await asyncio.sleep(1800)
            
            has_access, key_type, time_remaining = license_system.check_user_access(hardware_id)
            
            if not has_access:
                print("❌ \x1b[38;5;196mLicense expired! Shutting down bot...\x1b[38;5;255m")
                await bot.close()
                return
            
            if time_remaining and time_remaining.total_seconds() < 3600:  # Less than 1 hour remaining
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                print(f"⚠️ \x1b[38;5;208mLicense expires in {hours}h {minutes}m\x1b[38;5;255m")
                
        except Exception as e:
            print(f"Error checking license: {e}")
            await asyncio.sleep(300)  # Check again in 5 minutes on error

async def send_periodic_messages(channel_id):
    """Send periodic messages to a channel with fast delays"""
    while True:
        try:
            auto_channels = config.get("auto_channels", {})
            if channel_id not in auto_channels or not auto_channels[channel_id].get("enabled", True):
                break

            channel = bot.get_channel(int(channel_id))
            if channel:
                message = auto_channels[channel_id].get("message", "Auto message")
                await channel.send(message)

                # Fast delay: 0-60 seconds between messages
                delay_seconds = random.uniform(0, 60)
                print(f"Auto-channel message sent to {channel.name}. Next message in {delay_seconds:.1f} seconds.")
                await asyncio.sleep(delay_seconds)
                
                # Add 20 second delay for channel switching when multiple channels
                all_auto_channels = [ch_id for ch_id, ch_data in auto_channels.items() if ch_data.get("enabled", True)]
                if len(all_auto_channels) > 1:
                    await asyncio.sleep(20)  # 20 second delay between channels
                
            else:
                # If channel not found, wait before retrying
                await asyncio.sleep(60)

        except discord.Forbidden:
            print(f"No permission to send messages in channel {channel_id}")
            break
        except discord.HTTPException as e:
            print(f"HTTP error sending message to {channel_id}: {e}")
            await asyncio.sleep(120)  # Wait 2 minutes on HTTP errors
        except Exception as e:
            print(f"Error sending periodic message to {channel_id}: {e}")
            await asyncio.sleep(60)

def selfbot_menu(bot):
    if platform.system() == "Windows":
        os.system('cls')
    else:
        os.system('clear')
    print(f"""\n{Fore.RESET}
\x1b[38;5;127m ██▓███\x1b[38;5;255m   ██▓    ▄▄▄        ██████  ███▄ ▄███▓ ▄▄▄      
\x1b[38;5;127m▓██░  ██\x1b[38;5;255m▒▓██▒   ▒████▄    ▒██    ▒ ▓██▒▀█▀ ██▒▒████▄    
\x1b[38;5;127m▓██░ ██▓\x1b[38;5;255m▒▒██░   ▒██  ▀█▄  ░ ▓██▄   ▓██    ▓██░▒██  ▀█▄  
\x1b[38;5;127m▒██▄█▓▒\x1b[38;5;255m ▒▒██░   ░██▄▄▄▄██   ▒   ██▒▒██    ▒██ ░██▄▄▄▄██ 
\x1b[38;5;127m▒██▒ ░\x1b[38;5;255m  ░░██████▒▓█   ▓██▒▒██████▒▒▒██▒   ░██▒ ▓█   ▓██▒
\x1b[38;5;127m▒▓▒░ ░\x1b[38;5;255m  ░░ ▒░▓  ░▒▒   ▓▒█░▒ ▒▓▒ ▒ ░░ ▒░   ░  ░ ▒▒   ▓▒█░
\x1b[38;5;127m░▒ ░\x1b[38;5;255m     ░ ░ ▒  ░ ▒   ▒▒ ░░ ░▒  ░ ░░  ░      ░  ▒   ▒▒ ░
\x1b[38;5;127m░░\x1b[38;5;255m         ░ ░    ░   ▒   ░  ░  ░  ░      ░     ░   ▒   
\x1b[38;5;127m             \x1b[38;5;255m░  ░     ░  ░      ░         ░         ░  ░
                                                        \n""")

    print(f"""
    https://discord.gg/v2QwrUPUzk
 Linked --> \x1b[38;5;127m {bot.user} \x1b[38;5;255m 
 SelfBot Prefix -->\x1b[38;5;127m {prefix}\x1b[38;5;255m
 Nitro Sniper --> \x1b[38;5;48m Enabled \x1b[38;5;255m
 Extra Commands --> \x1b[38;5;48m Enabled \x1b[38;5;255m
 Anti-Ban --> \x1b[38;5;48m Enabled \x1b[38;5;255m
 Authentication --> \x1b[38;5;48m Telegram Bot \x1b[38;5;255m
 """)

bot = commands.Bot(command_prefix=prefix, description='not a selfbot', self_bot=True, help_command=None)

@bot.event
async def on_ready():
    if platform.system() == "Windows":
        ctypes.windll.kernel32.SetConsoleTitleW(f"SelfBot v{__version__} - Made By a5traa")
        os.system('cls')
    else:
        os.system('clear')

    selfbot_menu(bot)

    # Start license monitoring
    asyncio.create_task(monitor_license_expiration())

    # Start periodic messaging for all enabled auto channels
    auto_channels = config.get("auto_channels", {})
    for channel_id in auto_channels:
        if auto_channels[channel_id].get("enabled", True):
            asyncio.create_task(send_periodic_messages(channel_id))

@bot.event
async def on_message(message):
    if message.author.id in config["copycat"]["users"]:
        if message.content.startswith(config['prefix']):
            response_message = message.content[len(config['prefix']):]
            await message.reply(response_message)
        else:
            await message.reply(message.content)

    # Auto DM reply - only in DMs, sends once per user with cooldowns
    if config["afk"]["enabled"]:
        if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
            user_id = message.author.id
            current_time = time.time()

            # Initialize user data if not exists
            if user_id not in auto_dm_user_data:
                auto_dm_user_data[user_id] = {"last_reply": 0}

            # Cooldown: only reply once every 24 hours per user
            if current_time - auto_dm_user_data[user_id]["last_reply"] > 86400:  # 24 hours
                # Random delay between 1-60 seconds before sending
                delay_seconds = random.uniform(1, 60)
                await asyncio.sleep(delay_seconds)
                
                try:
                    reply_msg = await message.reply(config["afk"]["message"])
                    auto_dm_user_data[user_id]["last_reply"] = current_time
                    auto_dm_messages[user_id] = reply_msg
                except Exception as e:
                    print(f"Failed to send auto DM reply: {e}")
            return

    # Check for flag word in DMs to delete auto DM reply
    if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
        flag_word = config.get("flag_word", "").lower()
        if flag_word and flag_word in message.content.lower():
            if message.author.id in auto_dm_messages:
                try:
                    await auto_dm_messages[message.author.id].delete()
                    del auto_dm_messages[message.author.id]
                except:
                    pass
            return

    if message.author != bot.user:
        if str(message.author.id) in config["autoreply"]["users"]:
            autoreply_message = next(message_generator)
            await message.reply(autoreply_message)
            return

    if message.guild and message.guild.id == 1279905004181917808 and message.content.startswith(config['prefix']):
        await message.delete()
        await message.channel.send("> SelfBot commands are not allowed here. Thanks.", delete_after=5)
        return

    if message.author != bot.user and str(message.author.id) not in config["remote-users"]:
        return

    # Check for shortcuts
    if message.content.startswith(prefix):
        content_without_prefix = message.content[len(prefix):]
        parts = content_without_prefix.split(' ', 1)
        command_used = parts[0]

        if command_used in shortcuts:
            # Replace shortcut with actual command
            actual_command = shortcuts[command_used]
            if len(parts) > 1:
                # If there are additional arguments, append them
                new_content = f"{prefix}{actual_command} {parts[1]}"
            else:
                new_content = f"{prefix}{actual_command}"

            # Create a new message object with the replaced content
            message.content = new_content

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CommandNotFound):
        return

# All bot commands from the original main.py
@bot.command(aliases=['h'])
async def help(ctx):
    await ctx.message.delete()

    help_text = f"""
**Plasma SelfBot | Prefix: `{prefix}`**

**Commands:**
> :speech_balloon: `{prefix}autodmreply <message|stop>` - Set auto DM reply message (24h cooldown)
> :zap: `{prefix}shortcutcreate <command> <shortcut>` - Create a custom shortcut for a command
> :clipboard: `{prefix}listshortcuts` - List all custom shortcuts
> :wastebasket: `{prefix}shortcutdelete <shortcut>` - Delete a custom shortcut
> :robot: `{prefix}autochannelmessage <channel_id> <message>` - Enable auto-messaging in a channel
> :list: `{prefix}listchannels` - List all auto-message channels
> :no_entry: `{prefix}removechannel <channel_id>` - Remove auto-messaging from a channel

**Note:** Essential commands only!"""
    await ctx.send(help_text)











@bot.command()
async def shortcutcreate(ctx, command_name: str=None, shortcut: str=None):
    """Create a custom shortcut for a command"""
    await ctx.message.delete()

    if not command_name or not shortcut:
        await ctx.send(f"> **[ERROR]**: Invalid command.\n> __Command__: `{prefix}shortcutcreate <command_name> <shortcut>`", delete_after=5)
        return

    # Check if shortcut already exists
    if shortcut in shortcuts:
        await ctx.send(f"> **[ERROR]**: Shortcut `{shortcut}` already exists for command `{shortcuts[shortcut]}`", delete_after=5)
        return

    # Add shortcut
    shortcuts[shortcut] = command_name
    config["shortcuts"] = shortcuts
    save_config(config)

    await ctx.send(f"> **Shortcut created:** `{prefix}{shortcut}` → `{prefix}{command_name}`", delete_after=5)

@bot.command()
async def listshortcuts(ctx):
    """List all custom shortcuts"""
    await ctx.message.delete()

    if not shortcuts:
        await ctx.send("> **No shortcuts created yet**", delete_after=5)
        return

    shortcut_list = "**📎 CUSTOM SHORTCUTS**\n\n"
    for shortcut, command in shortcuts.items():
        shortcut_list += f"> ⚡ `{prefix}{shortcut}` → `{prefix}{command}`\n"

    await ctx.send(shortcut_list)

@bot.command()
async def shortcutdelete(ctx, shortcut: str=None):
    """Delete a custom shortcut"""
    await ctx.message.delete()

    if not shortcut:
        await ctx.send(f"> **[ERROR]**: Invalid command.\n> __Command__: `{prefix}shortcutdelete <shortcut|all>`", delete_after=5)
        return

    if shortcut.lower() == "all":
        if not shortcuts:
            await ctx.send("> **No shortcuts to delete**", delete_after=5)
            return

        removed_count = len(shortcuts)
        shortcuts.clear()
        config["shortcuts"] = shortcuts
        save_config(config)
        await ctx.send(f"> **Deleted all {removed_count} shortcuts**", delete_after=5)
        return

    if shortcut in shortcuts:
        command_name = shortcuts[shortcut]
        del shortcuts[shortcut]
        config["shortcuts"] = shortcuts
        save_config(config)
        await ctx.send(f"> **Shortcut deleted:** `{prefix}{shortcut}` (was for `{prefix}{command_name}`)", delete_after=5)
    else:
        await ctx.send(f"> **[ERROR]**: Shortcut `{shortcut}` not found", delete_after=5)

@bot.command()
async def autochannelmessage(ctx, channel_ids_str: str=None, *, message: str=None):
    await ctx.message.delete()

    if not channel_ids_str or not message:
        await ctx.send(f"> **[**ERROR**]**: Invalid command.\n> __Command__: `{prefix}autochannelmessage <channel_id(s)> <message>`", delete_after=5)
        return

    channel_ids = [cid.strip() for cid in channel_ids_str.split(',')]

    if "auto_channels" not in config:
        config["auto_channels"] = {}

    for channel_id in channel_ids:
        try:
            channel = bot.get_channel(int(channel_id))
            if not channel:
                await ctx.send(f"> **[**ERROR**]**: Channel not found with ID: `{channel_id}`", delete_after=5)
                continue

            config["auto_channels"][channel_id] = {
                "message": message,
                "enabled": True
            }
            save_config(config)

            await ctx.send(f"> **Auto-message enabled for channel:** `{channel.name}` (`{channel_id}`)\n> Message: `{message}`", delete_after=5)

            # Start periodic messaging for this channel if not already running
            if not any(task.get_name() == f"send_periodic_messages_{channel_id}" for task in asyncio.all_tasks()):
                asyncio.create_task(send_periodic_messages(channel_id), name=f"send_periodic_messages_{channel_id}")

        except ValueError:
            await ctx.send(f"> **[**ERROR**]**: Invalid channel ID format: `{channel_id}`", delete_after=5)
        except Exception as e:
            await ctx.send(f"> **[**ERROR**]**: An error occurred for channel `{channel_id}`: {e}", delete_after=5)

@bot.command()
async def listchannels(ctx):
    await ctx.message.delete()

    auto_channels = config.get("auto_channels", {})
    if not auto_channels:
        await ctx.send("> **No channels have auto-messaging enabled.**", delete_after=5)
        return

    channel_list = "**Channels with auto-messaging:**\n"
    for channel_id, channel_data in auto_channels.items():
        channel = bot.get_channel(int(channel_id))
        if channel:
            status = "✅ Active" if channel_data.get("enabled", True) else "❌ Disabled"
            message_preview = channel_data.get("message", "No message")[:30] + "..." if len(channel_data.get("message", "")) > 30 else channel_data.get("message", "No message")
            channel_list += f"> `{channel.name}` (`{channel_id}`) - {status}\n> Message: `{message_preview}`\n\n"
        else:
            channel_list += f"> Unknown Channel (`{channel_id}`) - ❌ Not Found\n\n"

    await ctx.send(channel_list, delete_after=15)

@bot.command()
async def removechannel(ctx, channel_id: str=None):
    await ctx.message.delete()

    if not channel_id:
        await ctx.send(f"> **[**ERROR**]**: Invalid command.\n> __Command__: `{prefix}removechannel <channel_id|all>`", delete_after=5)
        return

    auto_channels = config.get("auto_channels", {})

    if channel_id.lower() == "all":
        if not auto_channels:
            await ctx.send("> **No auto channels to remove**", delete_after=5)
            return

        removed_count = len(auto_channels)
        config["auto_channels"] = {}
        save_config(config)
        await ctx.send(f"> **Removed all {removed_count} auto channels**", delete_after=5)
        return

    if channel_id in auto_channels:
        del config["auto_channels"][channel_id]
        save_config(config)

        channel = bot.get_channel(int(channel_id))
        channel_name = channel.name if channel else "Unknown Channel"
        await ctx.send(f"> **Channel removed from auto-messaging:** `{channel_name}` (`{channel_id}`)", delete_after=5)
    else:
        await ctx.send(f"> **[**ERROR**]**: Channel `{channel_id}` is not in the auto-messaging list", delete_after=5)

@bot.command()
async def autodmreply(ctx, *, message: str=None):
    await ctx.message.delete()

    if not message:
        # Show current status when no message provided
        if config["afk"]["enabled"]:
            await ctx.send(f"> **Auto DM replies are ENABLED**\n> Current message: `{config['afk']['message']}`", delete_after=5)
        else:
            await ctx.send("> **Auto DM replies are DISABLED**", delete_after=5)
        return

    if message.lower() == "stop":
        config["afk"]["enabled"] = False
        save_config(config)
        await ctx.send("> **Auto DM replies have been disabled.**", delete_after=5)
    else:
        config["afk"]["enabled"] = True
        config["afk"]["message"] = message
        save_config(config)
        await ctx.send(f"> **Auto DM reply set to:** `{message}`", delete_after=5)

# Run the bot
if __name__ == "__main__":
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("❌ Invalid Discord token!")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")