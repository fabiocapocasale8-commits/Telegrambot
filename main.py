#!/usr/bin/env python3
"""
Plasma Bot - Telegram Authentication Setup
This script starts the Telegram bot for authentication instead of command line input.
"""
import os
import sys

# Use local license system only - no remote server needed

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

def main():
    """Main entry point - Start Telegram bot for authentication"""
    print("🤖 \x1b[38;5;127mPlasma Bot - Telegram Authentication Mode\x1b[38;5;255m")
    print("\n📱 Instead of entering credentials here, use the Telegram bot!")
    print("\n🔧 \x1b[38;5;127mSetup Instructions:\x1b[38;5;255m")
    print("1. Set your TELEGRAM_BOT_TOKEN environment variable")
    print("2. Start the Telegram bot authentication")
    print("3. Use /start in your Telegram bot chat")
    print("4. Follow the prompts to enter license key and Discord token")
    print("5. The Discord bot will start automatically after authentication")
    
    # Check if TELEGRAM_BOT_TOKEN is set
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not telegram_token:
        print("\n❌ \x1b[38;5;196mTELEGRAM_BOT_TOKEN environment variable not set!\x1b[38;5;255m")
        print("\x1b[38;5;127mPlease set your Telegram bot token and restart.\x1b[38;5;255m")
        print("\x1b[38;5;127mExample: export TELEGRAM_BOT_TOKEN='your_bot_token_here'\x1b[38;5;255m")
        return
    
    print(f"\n✅ \x1b[38;5;48mTelegram bot token found!\x1b[38;5;255m")
    print("🚀 \x1b[38;5;127mStarting Telegram authentication bot...\x1b[38;5;255m")
    
    # Import and run the Telegram bot
    try:
        from telegram_bot import main as run_telegram_bot
        run_telegram_bot()
    except ImportError as e:
        print(f"❌ \x1b[38;5;196mError importing Telegram bot: {e}\x1b[38;5;255m")
        print("Make sure telegram_bot.py exists and python-telegram-bot is installed")
    except Exception as e:
        print(f"❌ \x1b[38;5;196mError starting Telegram bot: {e}\x1b[38;5;255m")

if __name__ == "__main__":
    main()