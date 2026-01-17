import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["TOKEN"]
import re
import discord
from discord.ext import commands
import aiosqlite

# ----------------------------
# CONFIG (YOU DEFINE TOKEN)
# ----------------------------
# TOKEN = "YOUR TOKEN HERE"

GUILD_ID = 1461877032970354888

STAFF_ROLES = [
    1461877095474135071,
    1462144180133564750,
    1462144798021648456,
    1462144850659901551,
    1462145201509503221
]

DB_PATH = "tickets.db"
SAFE_CATEGORY = 1462144342071443577
STAFF_CHAT = 1462143929552998554
TICKET_CATEGORY = 1462148646647627816
TICKET_LOG_CHANNEL = 1462143929552998554
APP_CHANNEL = 1462148354971537630

BANNED_WORDS = [
    "nigger", "faggot", "kike", "tranny", "retard", "niga", "nigga",
    "fuck", "shit", "bitch", "cunt", "asshole", "pussy", "dick", "tits",
    "cum", "whore", "slut", "motherfucker", "bastard", "chink", "dyke",
    "kys", "kill yourself", "fag", "cuck", "simp", "incel", "thot",
    "dumbass", "jackass", "shithead", "twat", "wanker", "prick"
]

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# HELPERS
# ----------------------------
def log(msg: str):
    print(f"[LOG] {msg}")

def contains_banned(text: str):
    if not text:
        return False, None
    lower = text.lower()
    for word in BANNED_WORDS:
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, lower):
            return True, word
    return False, None

def is_staff(member: discord.Member):
    return any(role.id in STAFF_ROLES for role in member.roles)

# ----------------------------
# DATABASE
# ----------------------------
async def setup_db():
    log("Setting up database...")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                user_id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL
            )
        """)
        await db.commit()
    log("Database ready.")

# ----------------------------
# READY
# ----------------------------
@bot.event
async def on_ready():
    log(f"Bot online as {bot.user} ({bot.user.id})")
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    log("Slash commands synced.")
    await setup_db()
    print("--------------------------------------------------")

# ----------------------------
# STAFF APPLICATIONS
# ----------------------------
questions = [
    "1) Why do you want to be staff on this server specifically? (Not just 'to help')",
    "2) Do you have any past moderation experience? If yes, where and what did you actually do?",
    "3) How active are you on Discord? (Hours per day + time zone)",
    "4) How would you handle a situation where a staff member is abusing power?",
    "5) A user is breaking rules but is your friend. What do you do and why?",
    "6) What makes you a better pick than other applicants?"
]

@bot.tree.command(name="apply", description="Apply for staff")
@discord.app_commands.guilds(discord.Object(id=GUILD_ID))
async def apply(interaction: discord.Interaction):
    log(f"/apply used by {interaction.user} ({interaction.user.id})")
    await interaction.response.send_message("Check your DMs!", ephemeral=True)
    await send_application(interaction.user, 0, [])

async def send_application(user, idx, answers):
    if idx >= len(questions):
        channel = bot.get_channel(APP_CHANNEL)
        embed = discord.Embed(title="New Staff Application", color=discord.Color.blue())
        for i, q in enumerate(questions):
            embed.add_field(name=q, value=answers[i], inline=False)

        guild = bot.get_guild(GUILD_ID)
        member = guild.get_member(user.id)

        embed.add_field(name="User ID", value=str(user.id))
        embed.add_field(name="Joined Server", value=str(member.joined_at))

        await channel.send(embed=embed)
        await user.send("Your application has been submitted!")
        log(f"Application submitted for {user} ({user.id})")
        return

    embed = discord.Embed(title="Staff Application", description=questions[idx], color=discord.Color.green())
    await user.send(embed=embed)
    log(f"Sent question {idx + 1} to {user} ({user.id})")

    def check(m):
        return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)

    msg = await bot.wait_for("message", check=check)
    answers.append(msg.content)
    log(f"Received answer {idx + 1} from {user} ({user.id})")
    await send_application(user, idx + 1, answers)

# ----------------------------
# TICKETS
# ----------------------------
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create a Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        log(f"{user} clicked Create Ticket")

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT count FROM tickets WHERE user_id=?", (user.id,)) as cursor:
                row = await cursor.fetchone()

            if row:
                count = row[0] + 1
                await db.execute("UPDATE tickets SET count=? WHERE user_id=?", (count, user.id))
            else:
                count = 1
                await db.execute("INSERT INTO tickets(user_id, count) VALUES(?, ?)", (user.id, count))
            await db.commit()

        category = interaction.guild.get_channel(TICKET_CATEGORY)
        if category is None:
            log("Category not found.")
            return await interaction.response.send_message("Category not found.", ephemeral=True)

        channel_name = f"{user.name}_{count}"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
        }

        for role_id in STAFF_ROLES:
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)

        ticket_channel = await interaction.guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites
        )

        log(f"Ticket channel created: {ticket_channel.name} ({ticket_channel.id})")

        ping_channel = bot.get_channel(TICKET_LOG_CHANNEL)
        await ping_channel.send(f"New ticket in {ticket_channel.mention}")
        log("Pinged ticket channel.")

        embed = discord.Embed(title="Ticket Created", description="Click Close to close this ticket.", color=discord.Color.orange())
        view = CloseTicketView(ticket_channel.id, user.id)
        await ticket_channel.send(embed=embed, view=view)
        log("Sent close ticket embed.")

        await interaction.response.send_message("Ticket created!", ephemeral=True)

class CloseTicketView(discord.ui.View):
    def __init__(self, channel_id, opener_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.opener_id = opener_id

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        log(f"{interaction.user} clicked Close Ticket in {self.channel_id}")

        if not is_staff(interaction.user):
            log("Close ticket blocked: user not staff.")
            return await interaction.response.send_message("You aren't allowed to close tickets.", ephemeral=True)

        await interaction.response.send_modal(CloseModal(self.channel_id, self.opener_id))

class CloseModal(discord.ui.Modal, title="Close Ticket"):
    reason = discord.ui.TextInput(label="Reason", required=False, style=discord.TextStyle.paragraph)

    def __init__(self, channel_id, opener_id):
        super().__init__()
        self.channel_id = channel_id
        self.opener_id = opener_id

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value if self.reason.value else "No reason provided"
        log(f"Ticket close reason: {reason}")

        opener = await bot.fetch_user(self.opener_id)
        await opener.send(embed=discord.Embed(title="Ticket Closed", description=f"Reason: {reason}", color=discord.Color.red()))
        log("Sent DM to opener.")

        log_channel = bot.get_channel(STAFF_CHAT)
        await log_channel.send(f"Ticket closed: <#{self.channel_id}> by {interaction.user.mention} | Reason: {reason}")
        log("Logged ticket close.")

        await interaction.response.send_message("Ticket closed.", ephemeral=True)
        channel = bot.get_channel(self.channel_id)
        if channel:
            await channel.delete()
            log(f"Deleted channel {self.channel_id}")

# ----------------------------
# STAFF ACTIONS (IN STAFF LOG)
# ----------------------------
class StaffActionView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Timeout User", style=discord.ButtonStyle.gray, custom_id="timeout_user")
    async def timeout_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("You aren't staff.", ephemeral=True)
        await interaction.response.send_modal(TimeoutModal(self.user_id))

    @discord.ui.button(label="Kick User", style=discord.ButtonStyle.red, custom_id="kick_user")
    async def kick_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("You aren't staff.", ephemeral=True)
        member = interaction.guild.get_member(self.user_id)
        if member:
            await member.kick(reason="Staff action via bot")
            await interaction.response.send_message(f"Kicked <@{self.user_id}>", ephemeral=True)
            log(f"Kicked user {self.user_id}")
        else:
            await interaction.response.send_message("User not found.", ephemeral=True)

    @discord.ui.button(label="Ban User", style=discord.ButtonStyle.red, custom_id="ban_user")
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("You aren't staff.", ephemeral=True)
        member = interaction.guild.get_member(self.user_id)
        if member:
            await member.ban(reason="Staff action via bot")
            await interaction.response.send_message(f"Banned <@{self.user_id}>", ephemeral=True)
            log(f"Banned user {self.user_id}")
        else:
            await interaction.response.send_message("User not found.", ephemeral=True)

class TimeoutModal(discord.ui.Modal, title="Timeout User"):
    minutes = discord.ui.TextInput(label="Timeout minutes", required=True)

    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        minutes = int(self.minutes.value)
        member = interaction.guild.get_member(self.user_id)
        if member:
            await member.timeout(duration=discord.timedelta(minutes=minutes))
            await interaction.response.send_message(f"Timed out <@{self.user_id}> for {minutes} minutes.", ephemeral=True)
            log(f"Timed out user {self.user_id} for {minutes} minutes")
        else:
            await interaction.response.send_message("User not found.", ephemeral=True)

# ----------------------------
# MESSAGE FILTER + FORUM CHECK
# ----------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    log("on_message triggered")
    log(f"Author: {message.author} (bot={message.author.bot})")
    log(f"Channel: {message.channel} (type={message.channel.type})")
    log(f"Message ID: {message.id}")
    log(f"Content: {message.content}")

    # ----------------------------
    # FORUM / THREAD SCAN
    # ----------------------------
    if message.channel.type in (discord.ChannelType.forum, discord.ChannelType.public_thread):
        log("Forum/Thread message detected")

        title = message.channel.name
        body = message.content or ""

        log(f"Thread title: {title}")

        bad_title, banned_title = contains_banned(title)
        log(f"Title banned check: {bad_title} (word={banned_title})")

        if bad_title:
            await message.channel.delete()
            log("Deleted THREAD (title violation)")
            await message.author.send(
                f"{message.author.mention} Your message was blocked due to banned content."
            )
            log("DM sent to user")
            print("--------------------------------------------------\n")
            return

        bad_body, banned_body = contains_banned(body)
        log(f"Body banned check: {bad_body} (word={banned_body})")

        if bad_body:
            await message.delete()
            log("Deleted forum message (body violation)")
            await message.author.send(
                f"{message.author.mention} Your message was blocked due to banned content."
            )
            log("DM sent to user")

            staff_channel = bot.get_channel(STAFF_CHAT)
            view = StaffActionView(message.author.id)
            await staff_channel.send(
                f"Blocked message from {message.author.mention}: `{message.content}`",
                view=view
            )
            log("Sent staff log with actions")
            print("--------------------------------------------------\n")
            return

        log("Forum message passed filter")
        print("--------------------------------------------------\n")
        await bot.process_commands(message)
        return

    # ----------------------------
    # NORMAL MESSAGE FILTER
    # ----------------------------
    if isinstance(message.channel, discord.TextChannel):
        if message.channel.category_id != SAFE_CATEGORY:
            bad, banned = contains_banned(message.content)
            log(f"Normal message banned check: {bad} (word={banned})")

            if bad:
                await message.delete()
                log("Deleted message from user containing banned word.")

                await message.channel.send(
                    f"{message.author.mention} Your message was blocked due to banned content."
                )

                staff_channel = bot.get_channel(STAFF_CHAT)
                view = StaffActionView(message.author.id)

                await staff_channel.send(
                    f"Blocked message from {message.author.mention}: `{message.content}`",
                    view=view
                )
                log("Sent staff log with actions")
                print("--------------------------------------------------\n")
                return

    # ----------------------------
    # TICKET EMBED DM (ADMIN ONLY)
    # ----------------------------
    if isinstance(message.channel, discord.DMChannel):
        if message.author.id == 855487135821725707 and message.content.lower() == "ticketembed":
            log("Received ticketembed DM.")
            embed = discord.Embed(
                title="Ticket System",
                description="Click below to create a ticket.",
                color=discord.Color.blue()
            )
            view = TicketView()
            channel = bot.get_channel(1462148672505643028)
            await channel.send(embed=embed, view=view)
            log("Sent ticket embed.")
            await message.channel.send("Sent ticket embed.")

    await bot.process_commands(message)

# ----------------------------
# RUN BOT
# ----------------------------
bot.run(TOKEN)
