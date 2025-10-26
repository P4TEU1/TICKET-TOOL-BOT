import discord
from discord.ext import commands
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import View, Button
import json
import os

TOKEN = os.environ.get("BOT_TOKEN")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True  # important!

bot = commands.Bot(command_prefix="!", intents=intents)

CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    config = {"panels": {}}

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# View pentru butonul de deschis ticket
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Deschide Ticket", style=ButtonStyle.primary, custom_id="open_ticket"))

# View pentru butonul de închis ticket
class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Închide Ticket", style=ButtonStyle.danger, custom_id="close_ticket"))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

# Slash command pentru setup
@bot.tree.command(name="setup", description="Configurează un panel de ticket")
@app_commands.describe(category="ID-ul categoriei unde se vor crea ticket-urile")
async def setup(interaction: Interaction, category: str):
    guild = interaction.guild
    category_obj = guild.get_channel(int(category))
    if not category_obj or category_obj.type != discord.ChannelType.category:
        await interaction.response.send_message("ID de categorie invalid.", ephemeral=True)
        return
    config['panels'][str(guild.id)] = {"category_id": int(category)}
    save_config()

    # Embed personalizat cu P4TEU și detalii
    embed = discord.Embed(
        title="🎫 Ticket Support - P4TEU",
        description=(
            "Salut! 👋\n\n"
            "Acesta este sistemul de ticket pentru server.\n"
            "Apasă butonul de mai jos pentru a deschide un ticket.\n\n"
            "**Owner:** P4TEU\n"
            "**Ce poți face aici:** Raportare bug-uri, întrebări, sugestii.\n"
            "Un membru al staff-ului te va ajuta cât mai curând."
        ),
        color=0x1ABC9C  # culoare turcoaz
    )
    embed.set_footer(text="Ticket System by P4TEU")
    embed.set_thumbnail(url="https://i.imgur.com/your_logo.png")  # pune logo-ul tău aici

    await interaction.response.send_message(embed=embed, view=TicketView())

# Handler pentru click pe butoane
@bot.event
async def on_interaction(interaction: Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    if interaction.data["custom_id"] == "open_ticket":
        await interaction.response.defer(ephemeral=True)  # evită "This interaction failed"
        guild = interaction.guild
        panel = config['panels'].get(str(guild.id))
        if not panel:
            await interaction.followup.send("Panelul de ticket nu este configurat.", ephemeral=True)
            return
        category = guild.get_channel(panel['category_id'])
        if not category:
            await interaction.followup.send("Categoria de ticket nu a fost găsită.", ephemeral=True)
            return

        # verifică dacă userul are deja ticket (doar canale text)
        for c in guild.channels:
            if isinstance(c, discord.TextChannel):
                if c.topic and f"Ticket for {interaction.user.id}" in c.topic:
                    await interaction.followup.send(f"Ai deja un ticket: {c.mention}", ephemeral=True)
                    return

        # creează canalul de ticket
        channel_name = f"ticket-{interaction.user.name.lower()}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, read_message_history=True)
        }
        ticket_channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket for {interaction.user.id}"
        )

        embed = discord.Embed(
            title="Ticket deschis",
            description=f"Salut {interaction.user.mention}, un membru al staff-ului te va ajuta curând.",
            color=0x00AE86
        )
        await ticket_channel.send(embed=embed, view=CloseTicketView())
        await interaction.followup.send(f"Ticket creat: {ticket_channel.mention}", ephemeral=True)

    elif interaction.data["custom_id"] == "close_ticket":
        channel = interaction.channel
        if not hasattr(channel, "topic") or not channel.topic or "Ticket for" not in channel.topic:
            await interaction.response.send_message("Acest canal nu este un ticket.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        user_id = int(channel.topic.split("Ticket for ")[1])

        # Adună toate mesajele fără flatten()
        messages = [msg async for msg in channel.history(limit=None)]
        messages.reverse()

        transcript = "\n".join([f"[{m.created_at}] {m.author}: {m.content}" for m in messages])
        transcript_file = f"transcript-{channel.id}.txt"
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(transcript)

        # trimite transcript în DM
        user = await bot.fetch_user(user_id)
        try:
            await user.send(f"Transcriptul ticket-ului tău:", file=discord.File(transcript_file))
        except:
            pass
        await interaction.followup.send("Ticket închis și transcript trimis.", ephemeral=True)
        await channel.delete()
        os.remove(transcript_file)

bot.run(TOKEN)
