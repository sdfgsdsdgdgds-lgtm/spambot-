import os
import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Konfigurera via miljövariabler på Render
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
MESSAGE_TEXT = os.getenv("MESSAGE_TEXT", "Testspam!")
SPAM_DELAY = float(os.getenv("SPAM_DELAY", "1"))  # sekunder mellan meddelanden
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN or CHANNEL_ID == 0:
    raise RuntimeError("Saknar BOT_TOKEN eller CHANNEL_ID i miljövariablerna.")

@bot.event
async def on_ready():
    print(f"Inloggad som {bot.user} — startar spam-loop (interval: {SPAM_DELAY}s).")
    # starta spam-loopen i bakgrunden så on_ready inte blockeras
    bot.loop.create_task(spam_loop())

async def spam_loop():
    await bot.wait_until_ready()
    # Försök få kanalen. fetch om get misslyckas.
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(CHANNEL_ID)
        except Exception as e:
            print(f"Kunde inte hämta kanal {CHANNEL_ID}: {e}")
            return

    while not bot.is_closed():
        try:
            # Skicka @everyone + text
            await channel.send(f"@everyone {MESSAGE_TEXT}")
            await asyncio.sleep(SPAM_DELAY)
        except discord.errors.Forbidden:
            print("Saknar rättigheter att skicka eller nämna. Avslutar spam-loop.")
            break
        except discord.errors.HTTPException as e:
            # rate limit eller annat fel — backoff lite
            print(f"HTTPException vid skickande: {e}. Väntar 5s innan nytt försök.")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Oväntat fel i spam_loop: {e}. Väntar 5s.")
            await asyncio.sleep(5)

bot.run(TOKEN)


