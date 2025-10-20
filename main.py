import os
import discord
import re
import logging
from logging import Logger
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True

CHANNEL_TO_SCAN_CONTAINING_LINKS=1428314569364733984
CHANNEL_TO_SEND_LINKS_TO=1428318025634942977

URL_RE = re.compile(
    r'(?P<url>(?:https?://|ftp://|www\.)[^\s<>"]+)', re.IGNORECASE
)
USR_ID = re.compile(r"<@!?(\d+)>", re.IGNORECASE)

bot = commands.Bot(command_prefix="!", intents=intents)

BOT_TOKEN = os.environ.get("DISCORD_BOT_KEY")

def logger() -> Logger:
    _logger = logging.getLogger(__file__)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return _logger

LOGGER = logger()

async def extract_url(content):
    if not content:
        return None
    is_url = URL_RE.search(content)
    if not is_url:
        return None
    return content

async def process_message(message: discord.Message):
    if message.channel.id != CHANNEL_TO_SCAN_CONTAINING_LINKS:
        return
    LOGGER.info(f"Message is {message}")
    url = await extract_url(content=message.content)
    target_channel = bot.get_channel(CHANNEL_TO_SEND_LINKS_TO)
    original_channel = bot.get_channel(CHANNEL_TO_SCAN_CONTAINING_LINKS)
    if url is not None:
        LOGGER.info(f"Embeds size is: {len(message.embeds)}")
        # user_id = re.search(r"<@!?(\d+)>", message.content).group(1)
        await target_channel.send(content=f"User <@{message.author.id}> sends this message: {message.content}", silent=True)
        # await target_channel.send()
        await message.delete()
        await original_channel.send(content=f"<@{message.author.id}>, you reposted in the wrong neighborhood", silent=True)
        if message.author.id == 307858012721119233:
            await original_channel.send(content=f"<@{message.author.id}>, A kto to przyszedł? Pan maruda niszczyciel dobrej zabawy pogromca uśmiechów dzieci.")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    await process_message(message=message)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if after.author.bot:
        return
    await process_message(after)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    chat_channel = bot.get_channel(CHANNEL_TO_SCAN_CONTAINING_LINKS)
    if member.id == 307858012721119233 and before.channel is None and after.channel is not None:
        await chat_channel.send(
            content=f"<@{member.id}>, A kto to przyszedł? Pan maruda niszczyciel dobrej zabawy pogromca uśmiechów dzieci.")
        await chat_channel.send("<:mokerer:1429886210595098684>")

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
