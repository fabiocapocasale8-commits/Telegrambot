import asyncio
import os
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from src.remote_license_validator import get_hardware_id

# Admin configuration - Abel's setup
ADMIN_PHONE = "+49 176 76856881"
ADMIN_USER_ID = 6741982500  # Abel's admin ID (Melis @melis2002og)
# Add multiple admin user IDs as needed
ADMIN_USER_IDS = [6741982500]  # List of admin user IDs - Abel confirmed

# User session management
user_sessions = {}

class UserSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.waiting_for_license = False
        self.waiting_for_token = False
        self.license_validated = False
        self.discord_token = None
        self.hardware_id = get_hardware_id()
        self.processed_messages = set()  # Track processed message IDs
        self.processed_commands = set()  # Track processed command IDs

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"
    
    # Prevent duplicate command processing
    command_id = f"start_{update.message.message_id}"
    if user_id in user_sessions:
        session = user_sessions[user_id]
        if hasattr(session, 'processed_commands') and command_id in session.processed_commands:
            print(f"⚠️ Duplicate /start command from user {user_id}, ignoring")
            return
        if hasattr(session, 'processed_commands'):
            session.processed_commands.add(command_id)
    
    print(f"🔄 Processing /start command from {user_name} (ID: {user_id})")
    
    # Check if user is banned
    banned_users_file = "banned_users.json"
    if os.path.exists(banned_users_file):
        import json
        try:
            with open(banned_users_file, 'r') as f:
                banned_users = json.load(f)
            if str(user_id) in banned_users:
                ban_info = banned_users[str(user_id)]
                await update.message.reply_text(
                    f"🚫 **Access Denied**\n\n"
                    f"You have been banned from using this bot.\n"
                    f"Reason: {ban_info.get('reason', 'No reason provided')}\n\n"
                    f"Contact admin if you believe this is an error."
                )
                return
        except Exception:
            pass  # Continue if there's an error reading the ban file
    
    # Create or get user session
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    session = user_sessions[user_id]
    
    # Add command tracking for new sessions
    if not hasattr(session, 'processed_commands'):
        session.processed_commands = set()
    session.processed_commands.add(command_id)
    
    # Check if user already has valid license
    # Use the advanced license system
    import sys
    admin_path = os.path.join(os.path.dirname(__file__), 'admin_server')
    if admin_path not in sys.path:
        sys.path.append(admin_path)
    
    from admin.license_system import LicenseKeySystem
    license_system = LicenseKeySystem()
    hardware_id = session.hardware_id
    
    has_access, key_type, time_remaining = license_system.check_user_access(hardware_id)
    
    if has_access:
        await update.message.reply_text(
            f"🎉 Welcome back, {user_name}!\n\n"
            f"✅ Your {key_type} license is active\n"
            f"⏰ Time remaining: {format_time_remaining(time_remaining)}\n\n"
            f"🔑 Please enter your Discord token to continue:"
        )
        session.license_validated = True
        session.waiting_for_token = True
    else:
        # Create inline keyboard with redeem code button
        keyboard = [
            [InlineKeyboardButton("🎟️ Redeem Custom Code", callback_data="redeem_code")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"👋 Hello {user_name}! Welcome to Plasma Bot\n\n"
            "🔐 LICENSE VERIFICATION REQUIRED\n\n"
            "📝 Available license types:\n"
            "• 🕐 7-day access - Short term\n"
            "• 📅 30-day access - Monthly\n"
            "• ♾️ Permanent access - Lifetime\n\n"
            "⚠️ Each license works only once per device\n\n"
            "🔑 Please enter your license key or use the button below:",
            reply_markup=reply_markup
        )
        session.waiting_for_license = True

async def handle_custom_code(update: Update, context: ContextTypes.DEFAULT_TYPE, code_input: str) -> bool:
    """Handle custom code redemption - Returns True if code was processed, False otherwise"""
    if not update.effective_user or not update.message:
        return False
    
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"
    code_name = code_input.upper().strip()
    
    # Load custom codes
    import json
    custom_codes_file = "custom_codes.json"
    custom_codes = {}
    if os.path.exists(custom_codes_file):
        try:
            with open(custom_codes_file, 'r') as f:
                custom_codes = json.load(f)
        except:
            return False
    
    # Check if the input matches a custom code
    if code_name not in custom_codes:
        return False  # Not a custom code
    
    code_info = custom_codes[code_name]
    
    # Check if THIS USER already used this code (allow multiple users per code)
    user_usage_key = f"used_by_{user_id}"
    if code_info.get(user_usage_key, False):
        await update.message.reply_text(
            f"❌ **You Already Used This Code**\n\n"
            f"🏷️ Code: `{code_name}`\n"
            f"📅 You used this code on: {code_info.get(f'used_date_{user_id}', 'Unknown')}\n\n"
            f"💡 Each user can only use a code once."
        )
        return True
    
    # Check if code has expired
    if code_info.get("expiry_date"):
        expiry = datetime.fromisoformat(code_info["expiry_date"])
        if datetime.now() > expiry:
            await update.message.reply_text(
                f"⏰ **Code Expired**\n\n"
                f"🏷️ Code: `{code_name}`\n"
                f"📅 Expired on: {expiry.strftime('%Y-%m-%d %H:%M')}\n"
                f"💡 Contact admin for a new code."
            )
            return True
    
    # Redeem the code - validate the actual license key
    license_key = code_info["license_key"]
    session = user_sessions.get(user_id)
    if not session:
        user_sessions[user_id] = UserSession(user_id)
        session = user_sessions[user_id]
    
    # Use the license system to validate the key
    import sys
    admin_path = os.path.join(os.path.dirname(__file__), 'admin_server')
    if admin_path not in sys.path:
        sys.path.append(admin_path)
    
    from admin.license_system import LicenseKeySystem
    license_system = LicenseKeySystem()
    hardware_id = session.hardware_id
    
    is_valid, reason, time_remaining = license_system.validate_key(license_key, hardware_id)
    
    if is_valid:
        # Mark code as used by THIS USER (allow multiple users per code)
        user_usage_key = f"used_by_{user_id}"
        user_date_key = f"used_date_{user_id}"
        code_info[user_usage_key] = True
        code_info[user_date_key] = datetime.now().isoformat()
        
        # Also track in general usage list for admin visibility
        if "users_who_used" not in code_info:
            code_info["users_who_used"] = []
        code_info["users_who_used"].append({
            "user_id": user_id,
            "user_name": user_name,
            "used_date": datetime.now().isoformat()
        })
        
        # Save updated codes
        with open(custom_codes_file, 'w') as f:
            json.dump(custom_codes, f, indent=2)
        
        # Format time remaining
        time_text = format_time_remaining(time_remaining)
        
        await update.message.reply_text(
            f"🎉 **Code Redeemed Successfully!**\n\n"
            f"🏷️ Code: `{code_name}`\n"
            f"✅ Your {code_info['duration']} license is now active\n"
            f"⏰ Time remaining: {time_text}\n\n"
            f"🔑 Please enter your Discord token to continue:"
        )
        
        session.license_validated = True
        session.waiting_for_token = True
        session.waiting_for_license = False
        
        print(f"✅ User {user_name} (ID: {user_id}) redeemed custom code: {code_name}")
        
    else:
        await update.message.reply_text(
            f"❌ **Code Redemption Failed**\n\n"
            f"🏷️ Code: `{code_name}`\n"
            f"📝 Error: {reason}\n\n"
            f"💡 Contact admin for assistance."
        )
    
    return True

def format_time_remaining(time_remaining):
    """Format time remaining for display"""
    if not time_remaining:
        return "Permanent license - no expiration"
    
    days = time_remaining.days
    hours, remainder = divmod(time_remaining.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{days} days, {hours} hours, {minutes} minutes"

async def handle_license_key(update: Update, context: ContextTypes.DEFAULT_TYPE, license_key: str) -> None:
    """Handle license key validation"""
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)
    
    if not session:
        await update.message.reply_text("❌ Session expired. Please use /start to begin again.")
        return
    
    # Use the advanced license system
    import sys
    import os
    admin_path = os.path.join(os.path.dirname(__file__), 'admin_server')
    if admin_path not in sys.path:
        sys.path.append(admin_path)
    
    from admin.license_system import LicenseKeySystem
    license_system = LicenseKeySystem()
    hardware_id = session.hardware_id
    
    is_valid, reason, time_remaining = license_system.validate_key(license_key.strip(), hardware_id)
    
    if is_valid:
        await update.message.reply_text(
            "🎉 LICENSE ACTIVATED SUCCESSFULLY!\n\n"
            f"⏰ Expiration: {format_time_remaining(time_remaining)}\n"
            f"🔒 Hardware ID: {hardware_id[:8]}...\n\n"
            "🔑 Next Step: Please enter your Discord token:"
        )
        session.license_validated = True
        session.waiting_for_license = False
        session.waiting_for_token = True
    else:
        # Create inline keyboard for Discord and pricing
        keyboard = [
            [InlineKeyboardButton("🎮 Discord Server", url="https://discord.gg/qyD3ztRQE5")],
            [InlineKeyboardButton("💰 Key Prices", callback_data="show_prices")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ Hey, that key looks wrong!\n\n"
            f"What went wrong: {reason}\n\n"
            "🔑 Valid key format: 30M-XXXXXXXX-XXXXXXXX-XXXXXXXX\n\n"
            "💰 Need a key? Check prices below or join Discord!",
            reply_markup=reply_markup
        )

async def handle_discord_token(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    """Handle Discord token and start the bot"""
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)
    
    if not session:
        await update.message.reply_text("❌ Session expired. Please use /start to begin again.")
        return
    
    # Basic token validation
    if len(token) < 50 or not any(c.isdigit() for c in token):
        await update.message.reply_text(
            f"❌ Hey, that Discord token looks wrong!\n\n"
            "🔑 This is how a Discord token looks like:\n"
            f"MTExMjU4... (starts with letters/numbers, about 70 characters)\n\n"
            "📱 How to get your Discord token:\n"
            "1. Open Discord in browser (not app)\n"
            "2. Press F12 → Network tab\n"
            "3. Send any message\n"
            "4. Look for 'messages' request\n"
            "5. Copy 'authorization' header value\n\n"
            "🔄 Please try again with a valid Discord token:"
        )
        return
    
    session.discord_token = token
    session.waiting_for_token = False
    
    await update.message.reply_text(
        "🚀 Bot Configuration Complete!\n\n"
        "✅ License validated\n"
        "✅ Discord token received\n\n"
        "Your Plasma Bot is now starting...\n"
        "🔄 Launching Discord bot with automatic license monitoring..."
    )
    
    try:
        # Save the token for the main bot to use
        with open(f"token_{user_id}.txt", "w") as f:
            f.write(token)
        
        # Trigger main bot startup with this token
        await start_main_bot(token)
        
        # Send final confirmation
        await update.message.reply_text(
            "✅ Discord Bot Started Successfully!\n\n"
            "🤖 Your bot is now active and ready to use\n"
            "⚠️ The bot will automatically stop if your license expires\n"
            "📝 Use the command prefix in Discord to interact with your bot\n\n"
            "You can now close this chat - everything is running!"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to start Discord bot\n\n"
            f"Error: {str(e)}\n\n"
            "🔄 Please try again or contact support."
        )

async def start_main_bot(discord_token: str):
    """Start the main Discord bot with the provided token"""
    import subprocess
    import sys
    
    # Set environment variable for the main bot
    os.environ['DISCORD_TOKEN'] = discord_token
    
    # Start the main bot
    subprocess.Popen([sys.executable, "main_bot.py"])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all text messages"""
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Unknown"
    username = update.effective_user.username or "no_username"
    
    # Log user information for admin setup
    print(f"📱 Message from: {user_name} (@{username}) - User ID: {user_id}")
    
    session = user_sessions.get(user_id)
    
    if not session:
        await update.message.reply_text(
            "❌ No active session. Please use /start to begin."
        )
        return
    
    message_text = (update.message.text or "").strip()
    
    # Prevent processing empty messages
    if not message_text:
        return
    
    # Track processed messages to prevent duplicates
    message_id = update.message.message_id
    if not hasattr(session, 'processed_messages'):
        session.processed_messages = set()
    
    if message_id in session.processed_messages:
        print(f"⚠️ Duplicate message {message_id} from user {user_id}, ignoring")
        return
    
    session.processed_messages.add(message_id)
    
    # Limit stored message IDs to prevent memory bloat
    if len(session.processed_messages) > 50:
        session.processed_messages = set(list(session.processed_messages)[-25:])
    
    try:
        if session.waiting_for_license:
            # Check if it's a custom code first
            if await handle_custom_code(update, context, message_text):
                return
            # Otherwise handle as regular license key
            await handle_license_key(update, context, message_text)
        elif session.waiting_for_token:
            await handle_discord_token(update, context, message_text)
        else:
            # Check if it's a custom code even when not expecting license
            if await handle_custom_code(update, context, message_text):
                return
            await update.message.reply_text(
                "ℹ️ I'm not expecting any input right now.\n"
                "Use /start to begin the setup process."
            )
    except Exception as e:
        print(f"❌ Error handling message from {user_id}: {e}")
        await update.message.reply_text(
            "❌ An error occurred processing your message. Please try again or use /start to restart."
        )

def is_admin(update: Update) -> bool:
    """Check if user is admin based on user ID"""
    user = update.effective_user
    if not user:
        return False
    
    # Check against known admin user IDs
    if user.id in ADMIN_USER_IDS or user.id == ADMIN_USER_ID:
        return True
        
    return False

async def generate_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate license keys - Admin only"""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    # Parse command arguments
    args = context.args or []
    if len(args) < 1:
        await update.message.reply_text(
            "📝 **Key Generation Usage:**\n\n"
            "`/generate_key <type> [count]`\n\n"
            "**Types:**\n"
            "• `3mins` - 3-minute trial\n"
            "• `30mins` - 30-minute trial\n"
            "• `2h` - 2-hour license\n"
            "• `7d` - 7-day license\n"
            "• `30d` - 30-day license\n"
            "• `perm` - Permanent license\n\n"
            "**Examples:**\n"
            "`/generate_key 3mins` - Generate 1 three-minute trial\n"
            "`/generate_key 30mins 5` - Generate 5 thirty-minute trials\n"
            "`/generate_key 7d` - Generate 1 seven-day key\n"
            "`/generate_key perm` - Generate 1 permanent key"
        )
        return
    
    key_type = args[0].lower()
    count = int(args[1]) if len(args) > 1 else 1
    
    # Allow flexible time formats like 30mins, 3mins, 7d, 30d, perm
    valid_formats = ['7d', '30d', 'perm', 'permanent'] + [f'{i}mins' for i in range(1, 61)] + [f'{i}h' for i in range(1, 25)]
    if key_type not in valid_formats and not key_type.endswith(('mins', 'h', 'd', 'w', 'mo', 'y')):
        await update.message.reply_text(
            "❌ Invalid key type. Examples:\n"
            "• `3mins` - 3 minute key\n"
            "• `30mins` - 30 minute key  \n"
            "• `2h` - 2 hour key\n"
            "• `7d` - 7 day key\n"
            "• `30d` - 30 day key\n"
            "• `perm` - Permanent key"
        )
        return
    
    if count > 10:
        await update.message.reply_text("❌ Maximum 10 keys per request")
        return
    
    # Generate keys using the advanced license system with flexible time durations
    import sys
    import os
    admin_path = os.path.join(os.path.dirname(__file__), 'admin_server')
    if admin_path not in sys.path:
        sys.path.append(admin_path)
    
    from admin.license_system import LicenseKeySystem
    license_system = LicenseKeySystem()
    generated_keys = []
    
    for i in range(count):
        try:
            # Use the advanced system that supports flexible time formats
            key = license_system.generate_key(key_type)
            generated_keys.append(key)
            print(f"✅ Generated {key_type} key: {key}")
        except Exception as e:
            print(f"❌ Failed to generate {key_type} key: {e}")
            await update.message.reply_text(f"❌ Error generating key {i+1}: {str(e)}")
            return
    
    # Format response - support flexible key types
    key_type_name = key_type
    if key_type.endswith('mins'):
        key_type_name = f"{key_type[:-4]} Minute Access"
    elif key_type.endswith('h'):
        key_type_name = f"{key_type[:-1]} Hour Access"  
    elif key_type == '7d':
        key_type_name = '7-Day Access'
    elif key_type == '30d':
        key_type_name = '30-Day Access'
    elif key_type in ['perm', 'permanent']:
        key_type_name = 'Permanent Access'
    else:
        key_type_name = f"{key_type} Access"
    
    response = f"🔑 **{count} {key_type_name} Key(s) Generated:**\n\n"
    for i, key in enumerate(generated_keys, 1):
        response += f"`{i}.` `{key}`\n"
    
    response += f"\n⚠️ **Security Notice:**\n"
    response += f"• Keys are single-use only\n"
    response += f"• Distribute securely\n"
    response += f"• Keys expire based on type"
    
    await update.message.reply_text(response)

async def list_active_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List active users - Admin only"""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    # Import license system
    import sys
    import os
    admin_path = os.path.join(os.path.dirname(__file__), 'admin_server')
    if admin_path not in sys.path:
        sys.path.append(admin_path)
    
    from admin.license_system import LicenseKeySystem
    license_system = LicenseKeySystem()
    # This would need to be implemented in the license system
    await update.message.reply_text(
        "👥 **Active Users:**\n\n"
        "📊 Feature coming soon - will show:\n"
        "• Active license count\n"
        "• User hardware IDs\n"
        "• License expiration times\n"
        "• Usage statistics"
    )

async def show_prices_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle price button callback"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    pricing_text = (
        "💰 **KEY PRICES**\n\n"
        "🎯 **1 day key** → 5 invites\n"
        "⭐ **7 day key** → $5 or boost\n"
        "💎 **30 day key** → $20\n"
        "👑 **Permanent key** → $30\n\n"
        "💳 **Payments:**\n"
        "nitro/robux/giftcards\n\n"
        "📞 Contact admin to purchase!"
    )
    
    await query.edit_message_text(
        text=pricing_text,
        parse_mode='Markdown'
    )

async def revoke_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Revoke a license key - Admin only"""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    args = context.args or []
    if len(args) < 1:
        await update.message.reply_text(
            "📝 **Revoke Key Usage:**\n\n"
            "`/revoke_key <license_key>`\n\n"
            "**Example:**\n"
            "`/revoke_key 30M-XXXXXXXX-XXXXXXXX-XXXXXXXX`"
        )
        return
    
    license_key = args[0]
    
    # Use the advanced license system
    import sys
    import os
    admin_path = os.path.join(os.path.dirname(__file__), 'admin_server')
    if admin_path not in sys.path:
        sys.path.append(admin_path)
    
    from admin.license_system import LicenseKeySystem
    license_system = LicenseKeySystem()
    
    try:
        success = license_system.revoke_key(license_key)
        if success:
            await update.message.reply_text(
                f"✅ **Key Revoked Successfully**\n\n"
                f"🔑 Key: `{license_key}`\n"
                f"❌ This key is now invalid and cannot be used."
            )
        else:
            await update.message.reply_text(
                f"❌ **Key Not Found**\n\n"
                f"🔑 Key: `{license_key}`\n"
                f"This key doesn't exist in the system."
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error revoking key: {str(e)}")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ban a user from the bot - Admin only"""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    args = context.args or []
    if len(args) < 1:
        await update.message.reply_text(
            "📝 **Ban User Usage:**\n\n"
            "`/ban_user <user_id> [reason]`\n\n"
            "**Example:**\n"
            "`/ban_user 123456789 violation of terms`"
        )
        return
    
    user_id = args[0]
    reason = " ".join(args[1:]) if len(args) > 1 else "No reason provided"
    
    # Add to banned users list (simple implementation)
    banned_users_file = "banned_users.json"
    import json
    
    try:
        # Load existing banned users
        banned_users = {}
        if os.path.exists(banned_users_file):
            with open(banned_users_file, 'r') as f:
                banned_users = json.load(f)
        
        # Add new banned user
        banned_users[user_id] = {
            "banned_at": datetime.now().isoformat(),
            "reason": reason,
            "banned_by": update.effective_user.id
        }
        
        # Save banned users
        with open(banned_users_file, 'w') as f:
            json.dump(banned_users, f, indent=2)
        
        await update.message.reply_text(
            f"🚫 **User Banned Successfully**\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"📝 Reason: {reason}\n"
            f"❌ This user can no longer use the bot."
        )
        
        # Remove user from active sessions if present
        if int(user_id) in user_sessions:
            del user_sessions[int(user_id)]
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error banning user: {str(e)}")

async def create_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create custom named codes - Admin only"""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "📝 **Create Custom Code Usage:**\n\n"
            "`/create_code <code_name> <duration> [validity_days]`\n\n"
            "**Examples:**\n"
            "`/create_code WELCOME30 30mins` - 30min access, never expires\n"
            "`/create_code VIP7DAY 7d 30` - 7 day access, code expires in 30 days\n"
            "`/create_code TRIAL3MIN 3mins 7` - 3min access, code expires in 7 days\n\n"
            "**Durations:** 3mins, 30mins, 2h, 7d, 30d, perm\n"
            "**Validity:** How many days until the code itself expires (must be a NUMBER)"
        )
        return
    
    code_name = args[0].upper()
    duration = args[1].lower()
    validity_days = None
    
    # Parse validity days with error handling
    if len(args) > 2:
        try:
            validity_days = int(args[2])
            if validity_days <= 0:
                await update.message.reply_text(
                    "❌ **Invalid Validity Days**\n\n"
                    "Validity days must be a positive number.\n"
                    "Example: `/create_code MYCODE 30mins 7` (expires in 7 days)"
                )
                return
        except ValueError:
            await update.message.reply_text(
                f"❌ **Invalid Validity Days: `{args[2]}`**\n\n"
                "Validity days must be a NUMBER (how many days until code expires).\n\n"
                "**Correct format:**\n"
                "`/create_code <name> <duration> [days]`\n\n"
                "**Examples:**\n"
                "`/create_code WELCOME30 30mins` - never expires\n"
                "`/create_code VIP7DAY 7d 30` - expires in 30 days\n"
                "`/create_code TRIAL 3mins 7` - expires in 7 days"
            )
            return
    
    # Load existing custom codes
    import json
    custom_codes_file = "custom_codes.json"
    custom_codes = {}
    if os.path.exists(custom_codes_file):
        try:
            with open(custom_codes_file, 'r') as f:
                custom_codes = json.load(f)
        except:
            custom_codes = {}
    
    # Check if code already exists
    if code_name in custom_codes:
        await update.message.reply_text(
            f"❌ Code `{code_name}` already exists!\n"
            f"Use `/remove_code {code_name}` to remove it first or choose a different name."
        )
        return
    
    # Calculate expiry date if validity specified
    expiry_date = None
    if validity_days:
        expiry_date = (datetime.now() + timedelta(days=validity_days)).isoformat()
    
    # Generate the actual license key
    import sys
    admin_path = os.path.join(os.path.dirname(__file__), 'admin_server')
    if admin_path not in sys.path:
        sys.path.append(admin_path)
    
    from admin.license_system import LicenseKeySystem
    license_system = LicenseKeySystem()
    
    try:
        # Generate the actual license key
        license_key = license_system.generate_key(duration)
        
        # Store custom code information
        custom_codes[code_name] = {
            "license_key": license_key,
            "duration": duration,
            "created_date": datetime.now().isoformat(),
            "expiry_date": expiry_date,
            "used": False,
            "used_by": None,
            "used_date": None
        }
        
        # Save to file
        with open(custom_codes_file, 'w') as f:
            json.dump(custom_codes, f, indent=2)
        
        # Format response
        validity_text = f"\n🗓️ Code expires: {validity_days} days" if validity_days else "\n♾️ Code never expires"
        
        await update.message.reply_text(
            f"✅ **Custom Code Created Successfully!**\n\n"
            f"🏷️ Code Name: `{code_name}`\n"
            f"⏱️ Duration: {duration}\n"
            f"🔑 License Key: `{license_key}`{validity_text}\n\n"
            f"📋 Users can now redeem this code by typing: `{code_name}`"
        )
        
        print(f"✅ Admin created custom code: {code_name} ({duration})")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error creating code: {str(e)}")

async def list_codes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all custom codes - Admin only"""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    # Load custom codes
    import json
    custom_codes_file = "custom_codes.json"
    custom_codes = {}
    if os.path.exists(custom_codes_file):
        try:
            with open(custom_codes_file, 'r') as f:
                custom_codes = json.load(f)
        except:
            custom_codes = {}
    
    if not custom_codes:
        await update.message.reply_text("📋 No custom codes created yet.\n\nUse `/create_code` to create your first custom code!")
        return
    
    # Format code list
    response = "📋 **Active Custom Codes:**\n\n"
    from datetime import datetime
    now = datetime.now()
    
    for code_name, info in custom_codes.items():
        status_emoji = "✅"
        used_text = ""
        
        # Check if expired
        if info.get("expiry_date"):
            expiry = datetime.fromisoformat(info["expiry_date"])
            if now > expiry:
                status_emoji = "⏰"
                used_text = " (EXPIRED)"
        
        # Count how many users have used this code
        users_who_used = info.get("users_who_used", [])
        user_count = len(users_who_used)
        if user_count > 0:
            used_text += f" (Used by {user_count} user{'s' if user_count != 1 else ''})"
        
        response += f"{status_emoji} `{code_name}` - {info['duration']}{used_text}\n"
        response += "\n"
    
    response += "💡 Use `/code_info <name>` for details or `/remove_code <name>` to delete"
    
    await update.message.reply_text(response)

async def remove_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a custom code - Admin only"""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    args = context.args or []
    if len(args) < 1:
        await update.message.reply_text(
            "📝 **Remove Code Usage:**\n\n"
            "`/remove_code <code_name>`\n\n"
            "**Example:**\n"
            "`/remove_code WELCOME30`"
        )
        return
    
    code_name = args[0].upper()
    
    # Load custom codes
    import json
    custom_codes_file = "custom_codes.json"
    custom_codes = {}
    if os.path.exists(custom_codes_file):
        try:
            with open(custom_codes_file, 'r') as f:
                custom_codes = json.load(f)
        except:
            custom_codes = {}
    
    if code_name not in custom_codes:
        await update.message.reply_text(f"❌ Code `{code_name}` not found.\n\nUse `/list_codes` to see available codes.")
        return
    
    # Remove the code
    removed_info = custom_codes.pop(code_name)
    
    # Save updated file
    with open(custom_codes_file, 'w') as f:
        json.dump(custom_codes, f, indent=2)
    
    await update.message.reply_text(
        f"✅ **Code Removed Successfully!**\n\n"
        f"🗑️ Deleted: `{code_name}`\n"
        f"⏱️ Duration was: {removed_info['duration']}\n"
        f"🔑 License key: `{removed_info['license_key']}`"
    )
    
    print(f"🗑️ Admin removed custom code: {code_name}")

async def code_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed information about a custom code - Admin only"""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    args = context.args or []
    if len(args) < 1:
        await update.message.reply_text(
            "📝 **Code Info Usage:**\n\n"
            "`/code_info <code_name>`\n\n"
            "**Example:**\n"
            "`/code_info WELCOME30`"
        )
        return
    
    code_name = args[0].upper()
    
    # Load custom codes
    import json
    custom_codes_file = "custom_codes.json"
    custom_codes = {}
    if os.path.exists(custom_codes_file):
        try:
            with open(custom_codes_file, 'r') as f:
                custom_codes = json.load(f)
        except:
            custom_codes = {}
    
    if code_name not in custom_codes:
        await update.message.reply_text(f"❌ Code `{code_name}` not found.\n\nUse `/list_codes` to see available codes.")
        return
    
    info = custom_codes[code_name]
    from datetime import datetime
    
    # Format dates
    created = datetime.fromisoformat(info["created_date"]).strftime("%Y-%m-%d %H:%M")
    
    response = f"🔍 **Code Information: `{code_name}`**\n\n"
    response += f"🔑 License Key: `{info['license_key']}`\n"
    response += f"⏱️ Duration: {info['duration']}\n"
    response += f"📅 Created: {created}\n"
    
    if info.get("expiry_date"):
        expiry = datetime.fromisoformat(info["expiry_date"]).strftime("%Y-%m-%d %H:%M")
        response += f"⏰ Code Expires: {expiry}\n"
    else:
        response += f"♾️ Never Expires\n"
    
    # Show usage information
    users_who_used = info.get("users_who_used", [])
    if users_who_used:
        response += f"\n👥 **USAGE HISTORY** ({len(users_who_used)} user{'s' if len(users_who_used) != 1 else ''}):\n"
        for usage in users_who_used[-5:]:  # Show last 5 users
            used_date = datetime.fromisoformat(usage["used_date"]).strftime("%Y-%m-%d %H:%M")
            response += f"• {usage['user_name']} (ID: {usage['user_id']}) - {used_date}\n"
        if len(users_who_used) > 5:
            response += f"• ... and {len(users_who_used) - 5} more\n"
    else:
        response += f"\n✅ **AVAILABLE** (No users yet)\n"
    
    await update.message.reply_text(response)

async def redeem_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle redeem code button callback"""
    query = update.callback_query
    if not query or not query.message:
        return
    
    user_id = query.from_user.id
    
    await query.answer()
    
    # Create or get user session
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    
    try:
        await query.edit_message_text(
            "🎟️ **Redeem Custom Code**\n\n"
            "Please enter your custom code name:\n"
            "(Examples: WELCOME30, VIP7DAY, TRIAL)\n\n"
            "💡 Custom codes are special redemption codes created by admins"
        )
        
        # Set session to wait for custom code input
        user_sessions[user_id].waiting_for_license = True
    except Exception as e:
        print(f"❌ Error in redeem_code_callback: {e}")
        # Send new message instead of editing if edit fails
        await query.message.reply_text(
            "🎟️ **Redeem Custom Code**\n\n"
            "Please enter your custom code name:\n"
            "(Examples: WELCOME30, VIP7DAY, TRIAL)\n\n"
            "💡 Custom codes are special redemption codes created by admins"
        )
        user_sessions[user_id].waiting_for_license = True

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information"""
    if not update.message:
        return
    if is_admin(update):
        help_text = (
            "🤖 **Plasma Bot - Admin Panel**\n\n"
            "**User Commands:**\n"
            "/start - Begin bot setup process\n"
            "/help - Show this help message\n\n"
            "**Admin Commands:**\n"
            "/generate_key <type> [count] - Generate license keys\n"
            "/create_code <name> <duration> [days] - Create custom codes\n"
            "/list_codes - List all custom codes\n"
            "/remove_code <name> - Remove a custom code\n"
            "/code_info <name> - Show code details\n"
            "/revoke_key <key> - Revoke a license key\n"
            "/ban_user <user_id> [reason] - Ban a user\n"
            "/list_users - List active users\n\n"
            "**Setup Process:**\n"
            "1. Use /start command\n"
            "2. Enter license key when prompted\n"
            "3. Enter Discord token when prompted\n"
            "4. Bot starts automatically\n\n"
            "**License Types:**\n"
            "• 7d - 7-day access key\n"
            "• 30d - 30-day access key\n"
            "• perm - Permanent access key"
        )
    else:
        help_text = (
            "🤖 **Plasma Bot Setup Assistant**\n\n"
            "**Commands:**\n"
            "/start - Begin bot setup process\n"
            "/help - Show this help message\n\n"
            "**Setup Process:**\n"
            "1. Use /start command\n"
            "2. Enter your license key when prompted\n"
            "3. Enter your Discord token when prompted\n"
            "4. Bot will start automatically\n\n"
            "**License Types Available:**\n"
            "• 7-day access key\n"
            "• 30-day access key\n"
            "• Permanent access key"
        )
    await update.message.reply_text(help_text)

def main():
    """Main function to run the Telegram bot"""
    # Get bot token from environment or prompt user
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN environment variable not set!")
        print("Please set your Telegram bot token and restart.")
        return
    
    # Create application
    application = Application.builder().token(bot_token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("generate_key", generate_key))
    application.add_handler(CommandHandler("create_code", create_code))
    application.add_handler(CommandHandler("list_codes", list_codes))
    application.add_handler(CommandHandler("remove_code", remove_code))
    application.add_handler(CommandHandler("code_info", code_info))
    application.add_handler(CommandHandler("revoke_key", revoke_key))
    application.add_handler(CommandHandler("ban_user", ban_user))
    application.add_handler(CommandHandler("list_users", list_active_users))
    application.add_handler(CallbackQueryHandler(show_prices_callback, pattern="show_prices"))
    application.add_handler(CallbackQueryHandler(redeem_code_callback, pattern="redeem_code"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 Telegram bot started! Use /start in your bot chat to begin setup.")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()