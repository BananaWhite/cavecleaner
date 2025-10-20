# link_scanner.py
import re
import csv
import os
import asyncio
from datetime import datetime

import discord
from discord.ext import commands

# -------- CONFIG --------
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TARGET_CHANNEL_ID = 123456789012345678  # replace with the numeric channel ID
CSV_PATH = "captured_links.csv"
# ------------------------

# Regex to find URLs (reasonable balance between coverage & false positives)
URL_RE = re.compile(
    r'(?P<url>(?:https?://|ftp://|www\.)[^\s<>"]+)', re.IGNORECASE
)

# Ensure intents allow reading message content
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Keep a set of (message_id, url) to avoid duplicates in-memory.
# On restart the CSV is the source of truth; duplicates are checked when writing.
seen_pairs = set()

def ensure_csv_exists(path: str):
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["captured_at_utc", "guild_id", "channel_id", "message_id",
                             "author_id", "author_name", "url", "content_snippet"])

def read_seen_from_csv(path: str):
    if not os.path.exists(path):
        return
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row["message_id"]), row["url"])
            seen_pairs.add(key)

async def write_row(row: dict):
    # Append to CSV safely (non-blocking with run_in_executor)
    loop = asyncio.get_running_loop()
    def _write():
        # Simple duplicate check by reading last few lines could be expensive;
        # instead rely on seen_pairs in memory + a final safety pass.
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                row["captured_at_utc"],
                row["guild_id"],
                row["channel_id"],
                row["message_id"],
                row["author_id"],
                row["author_name"],
                row["url"],
                row["content_snippet"]
            ])
    await loop.run_in_executor(None, _write)

def extract_urls_from_text(text: str):
    if not text:
        return []
    found = [m.group("url") for m in URL_RE.finditer(text)]
    # Normalize 'www.' without scheme
    normalized = []
    for u in found:
        if u.startswith("www."):
            u = "http://" + u
        normalized.append(u)
    return normalized

async def process_message_for_links(message: discord.Message):
    # Only process messages in the target channel
    if message.channel.id != TARGET_CHANNEL_ID:
        return

    # Ignore bot messages
    if message.author and message.author.bot:
        return

    # 1) Extract links from text
    urls = extract_urls_from_text(message.content)

    # 2) Check attachments (images/files) for URLs (attachments have proxy_url and url)
    for att in message.attachments:
        # attachments are not external links in body but store direct URL to the file
        if att.url:
            urls.append(att.url)

    # 3) Remove duplicates while preserving order
    seen_local = set()
    unique_urls = []
    for u in urls:
        if u not in seen_local:
            seen_local.add(u)
            unique_urls.append(u)

    if not unique_urls:
        return

    # 4) Save each link (avoid duplicates using seen_pairs)
    rows_to_write = []
    for url in unique_urls:
        key = (message.id, url)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)

        row = {
            "captured_at_utc": datetime.utcnow().isoformat(),
            "guild_id": message.guild.id if message.guild else "",
            "channel_id": message.channel.id,
            "message_id": message.id,
            "author_id": message.author.id if message.author else "",
            "author_name": str(message.author) if message.author else "",
            "url": url,
            "content_snippet": (message.content[:200].replace("\n", " ")) if message.content else ""
        }
        rows_to_write.append(row)

    # Write rows asynchronously
    for r in rows_to_write:
        await write_row(r)
        print(f"[{r['captured_at_utc']}] Saved URL: {r['url']} (msg {r['message_id']})")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    ensure_csv_exists(CSV_PATH)
    read_seen_from_csv(CSV_PATH)
    print(f"Loaded {len(seen_pairs)} previously seen (message,url) pairs.")

@bot.event
async def on_message(message: discord.Message):
    # process incoming messages
    try:
        await process_message_for_links(message)
    except Exception as e:
        print("Error processing message:", e)
    # If you also use commands, you should process them:
    await bot.process_commands(message)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    # If someone edits and adds links, capture them
    try:
        # Only act if content changed
        if before.content == after.content:
            return
        await process_message_for_links(after)
    except Exception as e:
        print("Error processing edit:", e)

# Optional command to manually dump seen count
@bot.command(name="linkstats")
async def linkstats(ctx):
    if ctx.channel.id != TARGET_CHANNEL_ID:
        await ctx.send("This command only available in the target channel.")
        return
    await ctx.send(f"I've recorded {len(seen_pairs)} (message, url) pairs so far.")

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
