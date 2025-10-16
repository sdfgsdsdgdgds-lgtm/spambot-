import discord
import asyncio

TOKEN = "din_token_här"
CHANNEL_ID = 1234567890  # byt ut mot riktig kanal-ID
SPAM_MESSAGE = "Detta är ett spammeddelande"
SPAM_DELAY = 1  # sekunder

intents = discord.Intents.default()
intents.messages = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Inloggad som {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    while True:
        await channel.send(SPAM_MESSAGE)
        await asyncio.sleep(SPAM_DELAY)

client.run(TOKEN)


