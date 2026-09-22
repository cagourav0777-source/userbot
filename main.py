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

# --- CREDENTIALS (RENDER ENVIRONMENT VARIABLES) ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING")

if not API_ID or not API_HASH:
    raise ValueError("❌ ERROR: 'API_ID' / 'API_HASH' environment variables missing hain!")

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
    "bio": "",
    "photo": None,
}

PREFIX = ["."]


# ================= HELPER FUNCTIONS =================
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


async def safe_edit(message, text):
    """edit_text fail hone par crash na ho."""
    try:
        return await message.edit_text(text)
    except Exception:
        return message


async def delete_after_delay(message, delay: int = 120):
    """Background task: 120 seconds (2 mins) baad auto-delete karega."""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception:
        pass


# =========================================================
#  GROUP 0  ->  COMMANDS
# =========================================================

# ================= 1. AFK ON / OFF =================
@app.on_message(filters.me & filters.command("afk", prefixes=PREFIX), group=0)
async def set_afk(client, message):
    global IS_AFK, AFK_REASON, AFK_START_TIME
    IS_AFK = True
    AFK_USERS.clear()
    AFK_START_TIME = time.time()
    current_ist = datetime.now(IST).strftime("%I:%M %p")

    _, _, custom_reason = (message.text or "").partition(" ")
    clean_reason = custom_reason.strip()
    if clean_reason:
        AFK_REASON = clean_reason
    else:
        AFK_REASON = "Away from keyboard"

    await safe_edit(
        message,
        "💤 **ᴀғᴋ ᴍᴏᴅᴇ ᴀᴄᴛɪᴠᴀᴛᴇᴅ** 💤\n\n"
        f"📍 **ʀᴇᴀsᴏɴ :** `{AFK_REASON}`\n"
        f"🕒 **sɪɴᴄᴇ :** `{current_ist}`"
    )


@app.on_message(filters.me & filters.command(["unafk", "back"], prefixes=PREFIX), group=0)
async def manual_unafk(client, message):
    global IS_AFK
    IS_AFK = False
    AFK_USERS.clear()
    await safe_edit(message, "⚡ **ɪ'ᴍ ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ɴᴏᴡ!** 👋")


# ================= 2. CLONE & REVERT =================
@app.on_message(filters.me & filters.command(["copy", "clone"], prefixes=PREFIX), group=0)
async def copy_profile(client, message):
    global IS_CLONED

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await safe_edit(message, "❌ Kisi user ke message par reply karke `.clone` likho.")
        return

    status_msg = await safe_edit(message, "🔄 **Cloning profile...**")

    try:
        if not IS_CLONED:
            me = await client.get_chat("me")
            ORIGINAL_PROFILE["first_name"] = me.first_name or ""
            ORIGINAL_PROFILE["last_name"] = me.last_name or ""
            ORIGINAL_PROFILE["bio"] = me.bio or ""
            ORIGINAL_PROFILE["photo"] = None

            try:
                my_photos = [p async for p in client.get_chat_photos("me", limit=1)]
                if my_photos:
                    ORIGINAL_PROFILE["photo"] = await client.download_media(
                        my_photos[0].file_id,
                        file_name="original_dp.jpg"
                    )
            except Exception:
                pass

            IS_CLONED = True

        target_user = message.reply_to_message.from_user
        target_chat = await client.get_chat(target_user.id)

        await client.update_profile(
            first_name=target_chat.first_name or "User",
            last_name=target_chat.last_name or "",
            bio=target_chat.bio or ""
        )

        try:
            photos = [p async for p in client.get_chat_photos(target_chat.id, limit=1)]
            if photos:
                photo_path = await client.download_media(photos[0].file_id)
                await client.set_profile_photo(photo=photo_path)
                if photo_path and os.path.exists(photo_path):
                    os.remove(photo_path)
        except Exception:
            pass

        await safe_edit(status_msg, "✅ **Profile Cloned Successfully!**")
    except Exception as e:
        await safe_edit(status_msg, f"❌ **Error:** `{type(e).__name__}: {e}`")


@app.on_message(filters.me & filters.command(["revert", "restore"], prefixes=PREFIX), group=0)
async def revert_profile(client, message):
    global IS_CLONED

    if not IS_CLONED:
        await safe_edit(message, "❌ Koi clone backup nahi mila.")
        return

    status_msg = await safe_edit(message, "🔄 **Reverting profile...**")

    try:
        await client.update_profile(
            first_name=ORIGINAL_PROFILE["first_name"] or "User",
            last_name=ORIGINAL_PROFILE["last_name"],
            bio=ORIGINAL_PROFILE["bio"]
        )

        try:
            current = [p async for p in client.get_chat_photos("me", limit=1)]
            if current:
                await client.delete_profile_photos(current[0].file_id)
        except Exception:
            pass

        old_dp = ORIGINAL_PROFILE.get("photo")
        if old_dp and os.path.exists(old_dp):
            try:
                await client.set_profile_photo(photo=old_dp)
                os.remove(old_dp)
            except Exception:
                pass

        IS_CLONED = False
        await safe_edit(status_msg, "✅ **Profile Restored!**")
    except Exception as e:
        await safe_edit(status_msg, f"❌ **Error:** `{type(e).__name__}: {e}`")


# ================= 3. PURGE =================
@app.on_message(filters.me & filters.command("purge", prefixes=PREFIX), group=0)
async def purge_messages(client, message):
    if not message.reply_to_message:
        await safe_edit(message, "❌ Jahan se purge start karna hai us message par reply karo.")
        return

    chat_id = message.chat.id
    target_msg_id = message.reply_to_message.id
    cmd_msg_id = message.id

    msg_ids = []
    try:
        async for msg in client.get_chat_history(chat_id):
            if msg.id > cmd_msg_id:
                continue
            msg_ids.append(msg.id)
            if msg.id <= target_msg_id:
                break
    except Exception as e:
        await safe_edit(message, f"❌ **Error:** `{e}`")
        return

    deleted_count = 0
    for i in range(0, len(msg_ids), 100):
        batch = msg_ids[i:i + 100]
        try:
            deleted_count += await client.delete_messages(chat_id, batch)
        except Exception:
            pass
        await asyncio.sleep(0.2)

    actual_deleted = max(0, deleted_count - 1)
    try:
        status = await client.send_message(chat_id, f"🗑 **Purged {actual_deleted} messages!**")
        await asyncio.sleep(3)
        await status.delete()
    except Exception:
        pass


# ================= 4. PURGEME =================
@app.on_message(filters.me & filters.command(["purgeme", "pme"], prefixes=PREFIX), group=0)
async def purge_me_messages(client, message):
    _, _, raw_count = (message.text or "").partition(" ")
    raw_count = raw_count.strip()
    if raw_count.isdigit():
        count = int(raw_count)
    else:
        count = 1

    if count <= 0:
        await safe_edit(message, "❌ Count kam se kam 1 hona chahiye.")
        return

    chat_id = message.chat.id
    cmd_id = message.id
    msg_ids = []

    try:
        async for msg in client.get_chat_history(chat_id, limit=max(count * 5, 50)):
            if msg.id == cmd_id:
                continue
            if msg.outgoing or (msg.from_user and msg.from_user.is_self):
                msg_ids.append(msg.id)
                if len(msg_ids) >= count:
                    break
    except Exception as e:
        await safe_edit(message, f"❌ **Error:** `{type(e).__name__}: {e}`")
        return

    msg_ids.append(cmd_id)
    deleted = 0

    for i in range(0, len(msg_ids), 100):
        batch = msg_ids[i:i + 100]
        try:
            deleted += await client.delete_messages(chat_id, batch)
        except Exception:
            pass
        await asyncio.sleep(0.2)

    actual_deleted = max(0, deleted - 1)
    try:
        status = await client.send_message(chat_id, f"🗑 **Deleted {actual_deleted} of your messages!**")
        await asyncio.sleep(3)
        await status.delete()
    except Exception:
        pass


# ================= 5. PING =================
@app.on_message(filters.me & filters.command("ping", prefixes=PREFIX), group=0)
async def ping_cmd(client, message):
    start = time.time()
    m = await safe_edit(message, "🏓 **Pinging...**")
    ms = (time.time() - start) * 1000
    await safe_edit(m, f"🏓 **Pong!** `{ms:.0f} ms`")


# =========================================================
#  GROUP 1  ->  DM me khud message bhejo to Auto-Unafk
# =========================================================
@app.on_message(filters.me & filters.private, group=1)
async def auto_unafk_on_message(client, message):
    global IS_AFK
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


# =========================================================
#  GROUP 2  ->  AFK Auto-Reply (DMs) + 2 Min Auto-Delete
# =========================================================
@app.on_message(
    filters.private & filters.incoming & ~filters.me & ~filters.bot & ~filters.service,
    group=2
)
async def afk_reply_handler(client, message):
    if not IS_AFK:
        return
    if not message.from_user:
        return

    user_id = message.from_user.id
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
    try:
        sent_reply = await message.reply_text(reply_text)
        asyncio.create_task(delete_after_delay(sent_reply, delay=120))
    except Exception:
        pass


# ================= DUMMY WEB SERVER (RENDER 24/7) =================
async def start_web_server():
    port = int(os.getenv("PORT", "8080"))

    async def handle_request(reader, writer):
        try:
            await reader.read(1024)
            response = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 10\r\n\r\nBot Online"
            writer.write(response)
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_server(handle_request, "0.0.0.0", port)
    print(f"Web server active on port {port}")
    async with server:
        await server.serve_forever()


# ================= MAIN RUNNER =================
async def main():
    asyncio.create_task(start_web_server())
    await app.start()
    me = await app.get_me()
    print(f"✅ Userbot started as {me.first_name} (@{me.username})")
    await idle()
    await app.stop()


if __name__ == "__main__":
    loop.run_until_complete(main())
