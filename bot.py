# -*- coding: utf-8 -*-
"""
Discord Bot med auto-roll, anti-raid, timmeddelanden och slash-kommandon
Optimerad för 24/7-drift på Render
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import random
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

# ===== Miljövariabler =====
TOKEN = os.getenv('DISCORD_BOT_TOKEN')  # Ange token som miljövariabel på Render

# ===== Intents =====
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ===== KONFIGURATION =====
AUTO_ROLE_NAME = "Member"
ANTI_RAID_TIME_WINDOW = 60
ANTI_RAID_THRESHOLD = 5
HOURLY_MESSAGE_CHANNEL_NAME = "general"
HOURLY_MESSAGE = "SKICKA IN I exposé-📸"

# ===== ANTI-RAID =====
join_times = defaultdict(list)

def check_raid(guild_id):
    now = datetime.now()
    join_times[guild_id] = [t for t in join_times[guild_id] if now - t < timedelta(seconds=ANTI_RAID_TIME_WINDOW)]
    return len(join_times[guild_id]) >= ANTI_RAID_THRESHOLD

# ===== SPAM-KONFIG =====
# per-guild interval (sekunder). Default 1s (kan ändras med /setspam av admin)
spam_intervals = defaultdict(lambda: 1.0)  # sekunder, minst 1.0
# per-guild last send time
spam_last_sent = defaultdict(lambda: datetime.min)
# om spam är aktiverat per guild (kan också kontrolleras via loop-running)
spam_enabled = defaultdict(lambda: True)  # default True eftersom tidigare version startade det

MIN_SPAM_INTERVAL = 1.0  # säkerhetsgräns (sekunder)
MAX_BURST_MESSAGES = 5   # begränsa burst för att undvika rate limits

# ===== EVENTS =====
@bot.event
async def on_ready():
    print(f'✅ Bot inloggad som {bot.user.name} (ID: {bot.user.id})')
    try:
        synced = await bot.tree.sync()
        print(f'✅ Synkroniserade {len(synced)} slash-kommandon')
    except Exception as e:
        print(f'❌ Fel vid synkronisering: {e}')

    print('⏸️ Timmeddelanden är avstängda som standard – starta med /start')
    # Starta spam-loop (den kontrollerar spam_enabled och intervaller per guild)
    if not spammy_message.is_running():
        spammy_message.start()
        print('⚠️ Sekundmeddelanden-loopen startad (styr spam med /setspam, /spamstart, /spamstop)')

@bot.event
async def on_member_join(member):
    guild = member.guild

    # Auto-roll
    role = discord.utils.get(guild.roles, name=AUTO_ROLE_NAME)
    if role:
        try:
            await member.add_roles(role)
            print(f'✅ Gav rollen "{AUTO_ROLE_NAME}" till {member.name}')
        except Exception as e:
            print(f'❌ Kunde inte ge rollen till {member.name}: {e}')

    # Anti-raid
    join_times[guild.id].append(datetime.now())
    if check_raid(guild.id):
        alert_channel = discord.utils.get(guild.text_channels, name="admin") or (guild.text_channels[0] if guild.text_channels else None)
        if alert_channel:
            embed = discord.Embed(
                title="🚨 RAID VARNING 🚨",
                description=f"**{ANTI_RAID_THRESHOLD}+ användare** har joinat inom {ANTI_RAID_TIME_WINDOW} sekunder!",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Senaste medlemmen", value=f"{member.mention} ({member.name})", inline=False)
            embed.set_footer(text="Anti-Raid System")
            try:
                await alert_channel.send(embed=embed)
                print(f'⚠️ Raid upptäckt! Varning skickad till #{alert_channel.name}')
            except Exception as e:
                print(f'❌ Kunde inte skicka raid-varning: {e}')

# ===== TIMMEDDELANDEN =====
@tasks.loop(hours=1)
async def hourly_message():
    print("⏰ Försöker skicka timmeddelande...")
    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name=HOURLY_MESSAGE_CHANNEL_NAME)
        if channel:
            try:
                await channel.send(HOURLY_MESSAGE)
                print(f'✅ Skickade timmeddelande till #{channel.name} i {guild.name}')
            except Exception as e:
                print(f'❌ Kunde inte skicka timmeddelande i #{channel.name}: {e}')
        else:
            print(f'⚠️ Kanal "{HOURLY_MESSAGE_CHANNEL_NAME}" hittades inte i {guild.name}')

@hourly_message.before_loop
async def before_hourly_message():
    await bot.wait_until_ready()
    now = datetime.now()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    wait_seconds = (next_hour - now).total_seconds()
    print(f"⏳ Väntar {int(wait_seconds)} sekunder tills nästa hel timme ({next_hour.strftime('%H:%M')})...")
    await asyncio.sleep(wait_seconds)

# ===== KONFIGURERBART SPAM (loop körs ofta, men skickar per-guild enligt intervall) =====
@tasks.loop(seconds=1.0)
async def spammy_message():
    """
    Denna loop körs var 1s och kontrollerar per-guild om det är dags att skicka enligt spam_intervals.
    Detta gör att vi kan ha olika frekvenser per guild utan att starta flera loops.
    """
    now = datetime.now()
    for guild in bot.guilds:
        if not spam_enabled[guild.id]:
            continue

        interval = spam_intervals[guild.id]
        # säkerhetsgräns
        if interval < MIN_SPAM_INTERVAL:
            interval = MIN_SPAM_INTERVAL

        last = spam_last_sent[guild.id]
        elapsed = (now - last).total_seconds()
        if elapsed >= interval:
            channel = discord.utils.get(guild.text_channels, name=HOURLY_MESSAGE_CHANNEL_NAME)
            if not channel:
                # kanal finns inte
                continue
            try:
                # Skicka ett meddelande (kan ändras eller varieras)
                await channel.send("⏱️ Meddelande (spam) — interval: {:.1f}s".format(interval))
                spam_last_sent[guild.id] = datetime.now()
                print(f'Skickade spam i #{channel.name} ({guild.name}) — interval {interval}s')
            except discord.HTTPException as e:
                # Hantera rate limits / HTTP-fel
                print(f'❌ HTTPException vid spam i {guild.name}: {e} (väntar nästa gång)')
            except Exception as e:
                print(f'❌ Okänt fel vid spam i {guild.name}: {e}')

@spammy_message.before_loop
async def before_spammy_message():
    await bot.wait_until_ready()

# ===== SLASH-KOMMANDON =====
@bot.tree.command(name="hej", description="Säger hej till dig!")
async def hej(interaction: discord.Interaction):
    await interaction.response.send_message(f"👋 Hej {interaction.user.mention}! Trevligt att träffas!")

@bot.tree.command(name="ping", description="Visar botens latens")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! Latens: **{round(bot.latency*1000)}ms**")

@bot.tree.command(name="dice", description="Kastar en tärning (1-6)")
async def dice(interaction: discord.Interaction):
    result = random.randint(1,6)
    dice_emoji = ["","⚀","⚁","⚂","⚃","⚄","⚅"]
    await interaction.response.send_message(f"🎲 {interaction.user.mention} kastade tärningen och fick: **{result}** {dice_emoji[result]}")

@bot.tree.command(name="coinflip", description="Singlar slant")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["Krona","Klave"])
    emoji = "🪙" if result=="Krona" else "💿"
    await interaction.response.send_message(f"{emoji} {interaction.user.mention} singlade slant och fick: **{result}**!")

@bot.tree.command(name="joke", description="Berättar ett skämt")
async def joke(interaction: discord.Interaction):
    jokes = [
        "Varför kan inte cyklar stå själva? För att de är två-trötta! 🚴",
        "Vad säger en nolla till en åtta? Snyggt bälte! 👔",
        "Varför gick tomaten röd? Den såg salladdressingen! 🍅",
        "Vad är en pirats favoritbokstav? Rrrrr! 🏴‍☠️",
        "Hur får man en vävare att skratta? Berätta en vävande historia! 🕷️"
    ]
    await interaction.response.send_message(f"😄 Skämt:\n{random.choice(jokes)}")

# ===== START / STOPP TIMMEDDELANDEN =====
@bot.tree.command(name="start", description="Startar timmeddelanden (admin)")
async def start_hourly(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du måste vara admin för att använda detta kommando.", ephemeral=True)
        return

    if hourly_message.is_running():
        await interaction.response.send_message("🔁 Timmeddelanden körs redan.")
    else:
        hourly_message.start()
        await interaction.response.send_message("✅ Timmeddelanden har startats.")

@bot.tree.command(name="stopp", description="Stoppar timmeddelanden (admin)")
async def stop_hourly(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du måste vara admin för att använda detta kommando.", ephemeral=True)
        return

    if not hourly_message.is_running():
        await interaction.response.send_message("⏹️ Timmeddelanden är redan stoppade.")
    else:
        hourly_message.cancel()
        await interaction.response.send_message("🛑 Timmeddelanden har stoppats.")

# ===== SPAM-KOMMANDON (ADMIN) =====
@bot.tree.command(name="spamstart", description="Sätt igång spam-funktionen i den här servern (admin)")
async def spam_start(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du måste vara admin för att använda detta kommando.", ephemeral=True)
        return
    spam_enabled[interaction.guild_id] = True
    await interaction.response.send_message("✅ Spam aktiverat i denna server.")

@bot.tree.command(name="spamstop", description="Stoppa spam-funktionen i den här servern (admin)")
async def spam_stop(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du måste vara admin för att använda detta kommando.", ephemeral=True)
        return
    spam_enabled[interaction.guild_id] = False
    await interaction.response.send_message("🛑 Spam inaktiverat i denna server.")

@bot.tree.command(name="setspam", description="Ställ in spam-intervallet i sekunder (minst 1s) (admin)")
@app_commands.describe(seconds="Antal sekunder mellan meddelanden (t.ex. 1.0)")
async def set_spam(interaction: discord.Interaction, seconds: float):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du måste vara admin för att använda detta kommando.", ephemeral=True)
        return
    if seconds < MIN_SPAM_INTERVAL:
        await interaction.response.send_message(f"❌ Minsta tillåtna intervall är {MIN_SPAM_INTERVAL} sekunder.", ephemeral=True)
        return
    spam_intervals[interaction.guild_id] = float(seconds)
    await interaction.response.send_message(f"✅ Spam-intervallet är nu satt till {seconds:.1f} sekunder i denna server.")

@bot.tree.command(name="spamburst", description="Skicka flera meddelanden direkt (admin)")
@app_commands.describe(count="Hur många meddelanden (max 5)", message="Meddelandet att skicka")
async def spam_burst(interaction: discord.Interaction, count: int, message: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du måste vara admin för att använda detta kommando.", ephemeral=True)
        return
    if count < 1 or count > MAX_BURST_MESSAGES:
        await interaction.response.send_message(f"❌ Antalet måste vara mellan 1 och {MAX_BURST_MESSAGES}.", ephemeral=True)
        return

    channel = discord.utils.get(interaction.guild.text_channels, name=HOURLY_MESSAGE_CHANNEL_NAME)
    if not channel:
        await interaction.response.send_message(f"⚠️ Jag hittade ingen kanal som heter {HOURLY_MESSAGE_CHANNEL_NAME}.", ephemeral=True)
        return

    await interaction.response.send_message(f"🔃 Skickar {count} meddelanden...", ephemeral=True)
    sent = 0
    for i in range(count):
        try:
            await channel.send(message)
            sent += 1
            await asyncio.sleep(0.5)  # liten paus för att minska risk för rate-limit
        except discord.HTTPException as e:
            print(f'❌ HTTPException under spamburst: {e}')
            break
        except Exception as e:
            print(f'❌ Okänt fel under spamburst: {e}')
            break
    await channel.send(f"✅ Burst klar — skickade {sent}/{count} meddelanden.")

# ===== STARTA BOTEN =====
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: DISCORD_BOT_TOKEN hittades inte i miljövariablerna!")
    else:
        print("🚀 Startar Discord bot...")
        bot.run(TOKEN)


