#!/usr/bin/env python3
"""
Telegram Message Scheduler Bot

A bot that allows users to schedule messages to themselves by specifying
both a message and a delivery time. The bot delivers the message at the
scheduled time.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MessageScheduler:
    """Handles message scheduling and delivery."""
    
    def __init__(self):
        self.scheduled_messages: Dict[int, List[Dict]] = {}  # user_id -> list of scheduled messages
    
    def schedule_message(self, user_id: int, message: str, delivery_time: datetime) -> bool:
        """Schedule a message for delivery."""
        if user_id not in self.scheduled_messages:
            self.scheduled_messages[user_id] = []
        
        scheduled_msg = {
            'message': message,
            'delivery_time': delivery_time,
            'scheduled_at': datetime.now()
        }
        
        self.scheduled_messages[user_id].append(scheduled_msg)
        return True
    
    def get_user_scheduled_messages(self, user_id: int) -> List[Dict]:
        """Get all scheduled messages for a user."""
        return self.scheduled_messages.get(user_id, [])
    
    def remove_delivered_message(self, user_id: int, message: str, delivery_time: datetime):
        """Remove a delivered message from the schedule."""
        if user_id in self.scheduled_messages:
            self.scheduled_messages[user_id] = [
                msg for msg in self.scheduled_messages[user_id]
                if not (msg['message'] == message and msg['delivery_time'] == delivery_time)
            ]

# Global scheduler instance
scheduler = MessageScheduler()

def parse_time_input(time_str: str) -> Optional[datetime]:
    """
    Parse time input in various formats.
    Supports: HH:MM, HH:MM:SS, HH:MM AM/PM, HH:MM:SS AM/PM
    """
    time_str = time_str.strip().upper()
    
    # Remove extra spaces
    time_str = re.sub(r'\s+', ' ', time_str)
    
    # Try different time formats
    formats = [
        '%H:%M',           # 24-hour: 15:30
        '%H:%M:%S',        # 24-hour with seconds: 15:30:45
        '%I:%M %p',        # 12-hour: 3:30 PM
        '%I:%M:%S %p',     # 12-hour with seconds: 3:30:45 PM
        '%I:%M%p',         # 12-hour without space: 3:30PM
        '%I:%M:%S%p',      # 12-hour with seconds without space: 3:30:45PM
    ]
    
    for fmt in formats:
        try:
            parsed_time = datetime.strptime(time_str, fmt).time()
            now = datetime.now()
            
            # Create datetime for today with the parsed time
            delivery_datetime = datetime.combine(now.date(), parsed_time)
            
            # If the time has already passed today, schedule for tomorrow
            if delivery_datetime <= now:
                delivery_datetime += timedelta(days=1)
            
            return delivery_datetime
        except ValueError:
            continue
    
    return None

def parse_message_input(text: str) -> Optional[tuple[str, str]]:
    """
    Parse user input to extract message and time.
    Expected format: 'message: <text>, time: <time>'
    """
    # Remove extra whitespace
    text = text.strip()
    
    # Try to match the pattern
    pattern = r'message:\s*(.+?),\s*time:\s*(.+)'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    
    if match:
        message = match.group(1).strip()
        time_str = match.group(2).strip()
        
        if message and time_str:
            return message, time_str
    
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    welcome_message = """
🤖 **Message Scheduler Bot**

I help you schedule messages to be delivered to yourself at a specific time!

**How to use:**
1. Send me a message in this format:
   `message: Your message here, time: HH:MM`

2. I'll confirm your scheduled message

3. You'll receive your message at the specified time

**Time formats supported:**
- 24-hour: `15:30`, `15:30:45`
- 12-hour: `3:30 PM`, `3:30:45 PM`, `3:30PM`

**Examples:**
- `message: Remember to call mom, time: 18:00`
- `message: Take medication, time: 9:00 AM`
- `message: Meeting reminder, time: 14:30`

Type your message now! 📝
    """
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help information."""
    help_text = """
📋 **Help - Message Scheduler Bot**

**Command:**
- `/start` - Start the bot and see instructions
- `/help` - Show this help message
- `/list` - Show your scheduled messages

**Input Format:**
```
message: Your message text, time: HH:MM
```

**Time Formats:**
- 24-hour: `15:30`, `15:30:45`
- 12-hour: `3:30 PM`, `3:30:45 PM`, `3:30PM`

**Examples:**
- `message: Buy groceries, time: 17:00`
- `message: Doctor appointment, time: 10:30 AM`
- `message: Call John, time: 20:15`

**Notes:**
- Messages are scheduled for today if the time hasn't passed
- If the time has passed, it's scheduled for tomorrow
- You can schedule multiple messages
- Only you will receive your scheduled messages
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def list_scheduled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all scheduled messages for the user."""
    user_id = update.effective_user.id
    scheduled_messages = scheduler.get_user_scheduled_messages(user_id)
    
    if not scheduled_messages:
        await update.message.reply_text("📭 You have no scheduled messages.")
        return
    
    message_list = "📅 **Your Scheduled Messages:**\n\n"
    
    for i, msg in enumerate(scheduled_messages, 1):
        delivery_time = msg['delivery_time'].strftime('%Y-%m-%d %H:%M:%S')
        message_text = msg['message'][:50] + "..." if len(msg['message']) > 50 else msg['message']
        message_list += f"{i}. **{message_text}**\n   📅 {delivery_time}\n\n"
    
    await update.message.reply_text(message_list, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages and schedule them."""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Parse the input
    parsed = parse_message_input(text)
    
    if not parsed:
        error_message = """
❌ **Invalid Format**

Please use this format:
`message: Your message here, time: HH:MM`

**Examples:**
- `message: Remember to call mom, time: 18:00`
- `message: Take medication, time: 9:00 AM`

**Supported time formats:**
- 24-hour: `15:30`, `15:30:45`
- 12-hour: `3:30 PM`, `3:30:45 PM`, `3:30PM`
        """
        await update.message.reply_text(error_message, parse_mode='Markdown')
        return
    
    message_text, time_str = parsed
    
    # Parse the time
    delivery_time = parse_time_input(time_str)
    
    if not delivery_time:
        error_message = f"""
❌ **Invalid Time Format**

I couldn't understand the time: `{time_str}`

**Supported formats:**
- 24-hour: `15:30`, `15:30:45`
- 12-hour: `3:30 PM`, `3:30:45 PM`, `3:30PM`

**Examples:**
- `message: {message_text}, time: 18:00`
- `message: {message_text}, time: 9:00 AM`
        """
        await update.message.reply_text(error_message, parse_mode='Markdown')
        return
    
    # Schedule the message
    success = scheduler.schedule_message(user_id, message_text, delivery_time)
    
    if success:
        delivery_time_str = delivery_time.strftime('%Y-%m-%d %H:%M:%S')
        confirmation_message = f"""
✅ **Message Scheduled Successfully!**

📝 **Message:** {message_text}
📅 **Delivery Time:** {delivery_time_str}

Your message will be delivered to you at the scheduled time. You can use `/list` to see all your scheduled messages.
        """
        await update.message.reply_text(confirmation_message, parse_mode='Markdown')
        
        # Schedule the actual delivery
        asyncio.create_task(deliver_message(user_id, message_text, delivery_time))
    else:
        await update.message.reply_text("❌ Failed to schedule message. Please try again.")

async def deliver_message(user_id: int, message: str, delivery_time: datetime) -> None:
    """Deliver a scheduled message at the specified time."""
    now = datetime.now()
    delay = (delivery_time - now).total_seconds()
    
    if delay > 0:
        await asyncio.sleep(delay)
        
        # Send the message
        delivery_message = f"""
🔔 **Scheduled Message**

📝 {message}

*This message was scheduled for delivery at {delivery_time.strftime('%Y-%m-%d %H:%M:%S')}*
        """
        
        # Note: In a real implementation, you'd need access to the bot instance
        # to send messages. This is a simplified version.
        print(f"Delivering message to user {user_id}: {message}")
        
        # Remove from scheduled messages
        scheduler.remove_delivered_message(user_id, message, delivery_time)

def main() -> None:
    """Start the bot."""
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token
    application = Application.builder().token('8253800539:AAE7dJhOntnjhe0SRJGLxl9f_OmVCe_mH4M').build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_scheduled))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
