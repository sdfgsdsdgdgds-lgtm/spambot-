import os
import asyncio
import discord

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
MESSAGE_TEXT = os.getenv("MESSAGE_TEXT", "@everyone Test!")
SPAM_DELAY = float(os.getenv("SPAM_DELAY", "1"))

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        print("Can't find channel")
        return
    while True:
        try:
            await channel.send(MESSAGE_TEXT)
            await asyncio.sleep(SPAM_DELAY)
        except Exception as e:
            print("Error while sending:", e)
            await asyncio.sleep(5)

client.run(TOKEN)



