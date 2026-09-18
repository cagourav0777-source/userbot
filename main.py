import asyncio
import os
import time
from datetime import datetime, timezone, timedelta

# Python 3.12 / 3.14 loop setup
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from pyrogram import Client, filters, idle

# Indian Timezone (IST: UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# --- CREDENTIALS (RENDER ENVIRONMENT VARIABLES SE LEGA) ---
API_ID = int(os.getenv("API_ID", 30749174))
API_HASH = os.getenv("API_HASH", "6f40b570865526dc4e87f610e870e467")
SESSION_STRING = os.getenv("SESSION_STRING")

if not SESSION_STRING:
    raise ValueError("❌ ERROR: Render ke Environment Variables me 'SESSION_STRING' missing hai!")

app = Client(
    "my_account_session",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# AFK State Management
IS_AFK = False
AFK_REASON = ""
AFK_START_TIME = 0.0
AFK_USERS = {}
AFK_COOLDOWN = 15

# Profile Backup State
IS_CLONED = False
ORIGINAL_PROFILE = {
    "first_name": "",
    "last_name": "",
    "bio": ""
}


# ================= HELPER: READABLE TIME =================
def get_readable_time(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 and days == 0:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)


# Group me tag ya reply filter
def is_mentioned_or_replied(_, __, m):
    if m.mentioned:
        return True
    if m.reply_to_message and m.reply_to_message.from_user and m.reply_to_message.from_user.is_self:
        return True
    return False

mentioned_or_replied = filters.create(is_mentioned_or_replied)


# ================= 1. AFK / AUTO-REPLY SYSTEM =================
@app.on_message(filters.me & filters.command("afk", prefixes=["."]))
async def set_afk(client, message):
    global IS_AFK, AFK_REASON, AFK_START_TIME, AFK_USERS
    IS_AFK = True
    AFK_USERS.clear()
    AFK_START_TIME = time.time()
    current_ist = datetime.now(IST).strftime("%I:%M %p")
    
    if len(message.command) > 1:
        _, AFK_REASON = message.text.split(maxsplit=1)
    else:
        AFK_REASON = "Away from keyboard"

    await message.edit_text(
        "💤 **ᴀғᴋ ᴍᴏᴅᴇ ᴀᴄᴛɪᴠᴀᴛᴇᴅ** 💤\n\n"
        f"📍 **ʀᴇᴀsᴏɴ :** `{AFK_REASON}`\n"
        f"🕒 **sɪɴᴄᴇ :** `{current_ist}`"
    )


@app.on_message(filters.me & filters.command(["unafk", "back"], prefixes=["."]))
async def manual_unafk(client, message):
    global IS_AFK, AFK_REASON, AFK_USERS
    IS_AFK = False
    AFK_USERS.clear()
    await message.edit_text("⚡ **ɪ'ᴍ ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ɴᴏᴡ!** 👋")


# Kisi bhi chat me message bhejte hi AFK auto-off
@app.on_message(filters.me)
async def auto_unafk_on_message(client, message):
    global IS_AFK, AFK_USERS
    if not IS_AFK:
        return

    text = message.text or message.caption or ""
    if text.startswith(".") or text.startswith("/"):
        return

    IS_AFK = False
    AFK_USERS.clear()

    try:
        status_msg = await message.reply_text("⚡ **ɪ'ᴍ ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ɴᴏᴡ!** 👋")
        await asyncio.sleep(3)
        await status_msg.delete()
    except Exception:
        pass


# DMs + Groups me tag/reply par auto-reply
@app.on_message(
    (~filters.me & ~filters.bot & ~filters.service) & 
    (filters.private | (filters.group & mentioned_or_replied))
)
async def afk_reply_handler(client, message):
    global IS_AFK, AFK_REASON, AFK_START_TIME, AFK_USERS
    if not IS_AFK:
        return

    user_id = message.from_user.id if message.from_user else message.chat.id
    current_time = time.time()
    last_reply_time = AFK_USERS.get(user_id, 0)

    if (current_time - last_reply_time) < AFK_COOLDOWN:
        return

    AFK_USERS[user_id] = current_time

    elapsed_seconds = int(current_time - AFK_START_TIME)
    away_for_str = get_readable_time(elapsed_seconds)

    reply_text = (
        "ɪ ᴀᴍ ᴏғғʟɪɴᴇ ʀɪɢʜᴛ ɴᴏᴡ, ɪ ᴡɪʟʟ ᴄᴏᴍᴇ ᴏɴʟɪɴᴇ ᴀɴᴅ ʀᴇᴘʟʏ. 🕒\n\n"
        f"⏱️ **ᴀᴡᴀʏ ғᴏʀ :** `{away_for_str}`\n"
        f"📝 **ʀᴇᴀsᴏɴ :** `{AFK_REASON}`"
    )
    await message.reply_text(reply_text)


# ================= 2. CLONE & REVERT =================
@app.on_message(filters.me & filters.command(["copy", "clone"], prefixes=["."]))
async def copy_profile(client, message):
    global IS_CLONED
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.edit_text("❌ Reply to a valid user's message.")
        return

    status_msg = await message.edit_text("🔄 Cloning profile...")

    try:
        if not IS_CLONED:
            my_account = await client.get_chat("me")
            ORIGINAL_PROFILE["first_name"] = my_account.first_name or ""
            ORIGINAL_PROFILE["last_name"] = my_account.last_name or ""
            ORIGINAL_PROFILE["bio"] = my_account.bio or ""
            IS_CLONED = True

        target_user = message.reply_to_message.from_user
        target_chat = await client.get_chat(target_user.id)

        await client.update_profile(
            first_name=target_chat.first_name or "",
            last_name=target_chat.last_name or "",
            bio=target_chat.bio or ""
        )

        photos = [p async for p in client.get_chat_photos(target_chat.id, limit=1)]
        if photos:
            photo_path = await client.download_media(photos[0].file_id)
            await client.set_profile_photo(photo=photo_path)
            if os.path.exists(photo_path):
                os.remove(photo_path)

        await status_msg.edit_text("✅ **Profile Cloned Successfully!**")
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")


@app.on_message(filters.me & filters.command(["revert", "restore"], prefixes=["."]))
async def revert_profile(client, message):
    global IS_CLONED
    if not IS_CLONED:
        await message.edit_text("❌ No clone backup found.")
        return

    status_msg = await message.edit_text("🔄 Reverting profile...")

    try:
        await client.update_profile(
            first_name=ORIGINAL_PROFILE["first_name"],
            last_name=ORIGINAL_PROFILE["last_name"],
            bio=ORIGINAL_PROFILE["bio"]
        )

        my_photos = [p async for p in client.get_chat_photos("me", limit=1)]
        if my_photos:
            await client.delete_profile_photos(photo_ids=my_photos[0].file_id)

        IS_CLONED = False
        await status_msg.edit_text("✅ **Profile Restored!**")
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")


# ================= 3. PURGE (FAST DELETE) =================
@app.on_message(filters.me & filters.command("purge", prefixes=["."]))
async def purge_messages(client, message):
    if not message.reply_to_message:
        await message.edit_text("❌ Reply to the message to start purge.")
        return

    start_id = min(message.reply_to_message.id, message.id)
    end_id = max(message.reply_to_message.id, message.id)
    chat_id = message.chat.id

    msg_ids = list(range(start_id, end_id + 1))
    deleted_count = 0

    for i in range(0, len(msg_ids), 100):
        batch = msg_ids[i:i+100]
        try:
            await client.delete_messages(chat_id, batch)
            deleted_count += len(batch)
        except Exception:
            pass
        await asyncio.sleep(0.1)

    status = await client.send_message(chat_id, f"🗑 **Purged {deleted_count} messages!**")
    await asyncio.sleep(3)
    await status.delete()


# ================= DUMMY WEB SERVER (RENDER 24/7) =================
async def start_web_server():
    port = int(os.getenv("PORT", 8080))
    async def handle_request(reader, writer):
        await reader.read(100)
        response = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 10\r\n\r\nBot Online"
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_request, "0.0.0.0", port)
    print(f"Web server active on port {port}")
    async with server:
        await server.serve_forever()


# ================= MAIN RUNNER =================
async def main():
    asyncio.create_task(start_web_server())
    await app.start()
    print("Userbot started successfully on Render!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop.run_until_complete(main())
