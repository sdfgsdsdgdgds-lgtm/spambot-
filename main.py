import discord
from discord.ext import commands
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
MESSAGE_TEXT = os.getenv("MESSAGE_TEXT", "🚨 Testspam!")
SPAM_DELAY = 1  # varje sekund

spamming = False

@bot.event
async def on_ready():
    print(f"Inloggad som {bot.user}")
    await bot.tree.sync()

@bot.tree.command(name="start_spamm", description="Startar spam med @everyone")
async def start_spamm(interaction: discord.Interaction):
    global spamming
    if spamming:
        await interaction.response.send_message("Spam kör redan!", ephemeral=True)
        return

    spamming = True
    await interaction.response.send_message("🚨 Startar spam!", ephemeral=True)
    channel = bot.get_channel(CHANNEL_ID)

    while spamming:
        await channel.send(f"@everyone {MESSAGE_TEXT}")
        await asyncio.sleep(SPAM_DELAY)

@bot.tree.command(name="stop_spamm", description="Stoppar spammet")
async def stop_spamm(interaction: discord.Interaction):
    global spamming
    spamming = False
    await interaction.response.send_message("🛑 Stoppade spammet.", ephemeral=True)

bot.run(TOKEN)
