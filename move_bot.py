#!/usr/bin/env python3
########################################
#
# This is the master file for @MoveBot 1.5#4299 (896420954396307546)
# Use any modifications at your own risk!
# Self-hosted implementations are not supported!
# Create by @Nexas#6792 (221132862567612417)
# Database functions added by @Sojhiro#2008 (206797306173849600)
# More functionality and hosting provided by @SadPuppies | beta<at>timpi.io#7339 (948208421054865410)
#
########################################

from concurrent.futures import thread
import os
import io
import itertools
import json
import discord
import requests
import asqlite # using asqlite now since it is asynchronous
import asyncio # needed for sleep functions
from contextlib import closing
from discord import Thread
from discord import app_commands
from discord.ext import commands # this upgrades from `client` to `bot` (per Rapptz's recommendation)
from dotenv import load_dotenv # this keeps the api_token secret, and also allows for user configs
import logging # pipe all of the output to a log file to make reading through it easier
from typing import Literal, Optional, List

load_dotenv()

LOG_PATH = os.getenv('LOG_PATH')

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename=LOG_PATH, encoding='UTF-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

TOKEN = os.getenv('DISCORD_TOKEN')
STATS_TOKEN = os.getenv('STATS_TOKEN')
STATS_ID = os.getenv('MOVEBOT_STATS_ID')
ADMIN_ID = os.getenv('ADMIN_UID')
BOT_ID = os.getenv('MOVEBOT_ID')
DB_PATH = os.getenv('DB_PATH')
DELETE_ORIGINAL = os.getenv('DELETE_ORIGINAL')
MAX_MESSAGES = os.getenv('MAX_MESSAGES')
PRESENCE_MESSAGE = os.getenv('PRESENCE_MESSAGE')
PRESENCE_MESSAGE = PRESENCE_MESSAGE if PRESENCE_MESSAGE is not None else 'for spoilers | /help'

available_prefs = {
    "notify_dm": "0",
    "embed_message": "0",
    "move_message": "MESSAGE_USER, your message has been moved to DESTINATION_CHANNEL by MOVER_USER",
    "strip_ping": "0",
    "delete_original": "1" # allows to original message to be preserved @SadPuppies 5/31/23
}
pref_help = {
    "notify_dm": """
**name:** `notify_dm`
**value:**
 `0`  Sends move message in channel
 `1`  Sends move message as a DM
 `2`  Don't send any message

**example:**
`/pref set notify_dm 1`
    """,
    "embed_message": """
**name:** `embed_message`
**value:**
 `0`  Does not embed move message
 `1`  Embeds move message

**example:**
`/pref set embed_message 1`
    """,
    "move_message": """
**name:** `move_message`
**value:** main message sent to the user.
**variables:** `MESSAGE_USER`, `DESTINATION_CHANNEL`, `MOVER_USER`

**example:**
`/pref set send_message MESSAGE_USER, your message belongs in DESTINATION_CHANNEL and was moved by MOVER_USER`
    """,
    "strip_ping": """
**name:** `strip_ping`
**value:**
`0` Do not strip pings
`1` Strip 'everyone' and 'here' pings

**example:**
`/pref set strip_ping 1`
    """,
    #`delete_original` added to allow users to merely copy @SadPuppies 4/9/23
    "delete_original": """
**name:** `delete_original`
**value:**
`0` Do not delete the original (basically turns the bot into CopyBot)
`1` Deletes the original message (the default functionality)

**example:**
`/pref set delete_original 0`
    """
}
prefs = {}
#upgrading to `asqlite` <https://github.com/Rapptz/asqlite> because it has `async`/`await` functionality. This will alleviate concurrency errors @SadPuppies 4/9/23
async def db_init():
    async with asqlite.connect(DB_PATH) as connection:
        #connection.row_factory = sqlite3.Row
        async with connection.cursor() as cursor:
            await cursor.execute( #added all onto same row, this prevents duplicate g_id / pref_name entries. ALso removed `key` column, it is redundant (all guild IDs are unique)
                """CREATE TABLE IF NOT EXISTS prefs (
                guild_id INTEGER PRIMARY KEY,
                notify_dm TEXT,
                embed_message TEXT,
                move_message TEXT,
                strip_ping TEXT,
                delete_original TEXT)"""
            ) #All guild preferences go on one line now. This will eliminate all duplicate entries @SadPuppies 4/9/23
            #setting some of these values to `INT` type will be tedious at best because `move_message` will have to be `TEXT` and specifying different types within a single `update pref` function (see below) is beyond this author's expertise @SadPuppies 4/9/23
            await cursor.execute("SELECT * FROM prefs")
            rows = await cursor.fetchall()
            for row in rows:
                g_id = int(row["guild_id"])
                if g_id not in prefs:
                    prefs[g_id] = {}
                prefs[g_id]["notify_dm"] = [str(row["notify_dm"])]
                prefs[g_id]["embed_message"] = [str(row["embed_message"])]
                prefs[g_id]["move_message"] = [str(row["move_message"])]
                prefs[g_id]["strip_ping"] = [str(row["strip_ping"])]
                prefs[g_id]["delete_original"] = [str(row["delete_original"])]
        await cursor.close()
        await connection.commit()

asyncio.run(db_init())
async def _get_pref(guild_id, pref):
    return prefs[guild_id][pref] if guild_id in prefs and pref in prefs[guild_id] else available_prefs[pref]

async def update_pref(guild_id, pref, value): #This needs to be it's own function so that it can be `async`
    if guild_id not in prefs:
        prefs[guild_id] = available_prefs 
        prefs[guild_id][pref] = value
        async with asqlite.connect(DB_PATH) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(f"INSERT OR IGNORE INTO prefs VALUES (?, ?, ?, ?, ?, ?)",
                                        (int(guild_id),
                                         prefs[guild_id]["notify_dm"],
                                         prefs[guild_id]["embed_message"],
                                         prefs[guild_id]["move_message"],
                                         prefs[guild_id]["strip_ping"],
                                         prefs[guild_id]["delete_original"]
                                        )
                                    )
                await cursor.close()
                await connection.commit()
    else:
        async with asqlite.connect(DB_PATH) as connection:
            async with connection.cursor() as cursor:
                sql = f"UPDATE prefs SET {pref} = {value} WHERE guild_id = {int(guild_id)}"
                await cursor.execute(sql)
                await cursor.close()
                await connection.commit()

async def reset_prefs(guild_id):
    async with asqlite.connect(DB_PATH) as connection:
        async with connection.cursor() as cursor:
            sql = f"DELETE FROM prefs WHERE guild_id = {int(guild_id)}"
            await cursor.execute(sql)
            await cursor.close()
            await connection.commit()

async def update_move_msg_pref(guild_id, moved_message):
    mm = ""
    for word in moved_message:
        mm += word
    if guild_id not in prefs:
        prefs[guild_id] = available_prefs
        prefs[guild_id]['move_message'] = mm
        async with asqlite.connect(DB_PATH) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(f"INSERT OR IGNORE INTO prefs VALUES (?, ?, ?, ?, ?, ?)",
                                        (int(guild_id),
                                         prefs[guild_id]["notify_dm"],
                                         prefs[guild_id]["embed_message"],
                                         prefs[guild_id]["move_message"],
                                         prefs[guild_id]["strip_ping"],
                                         prefs[guild_id]["delete_original"]
                                        )
                                    )
                await cursor.close()
                await connection.commit()
    else:
        prefs[guild_id]['move_message'] = mm
        async with asqlite.connect(DB_PATH) as connection:
            async with connection.cursor() as cursor:
                sql = f"UPDATE prefs SET move_message = {mm} where guild_id = {int(guild_id)}"
                await cursor.execute(sql)
                await cursor.close()
                await connection.commit()

pref_help_description = """
**Preferences**
You can set bot preferences like so:
`/pref set [preference name] [preference value]`
"""
for k, v in pref_help.items():
    pref_help_description = pref_help_description + v

class movebot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents, max_messages=int(MAX_MESSAGES))
        self.synced = False
        self.tree = app_commands.CommandTree(self)
        self.admin = None
        self.group_pref = app_commands.Group(name='pref', description='Preferences')

    async def on_ready(self):
        await self.wait_until_ready()
        print(f'{self.user} has connected to Discord!')
        if not self.synced:
            self.tree.add_command(self.group_pref)
            await self.tree.sync()
            self.synced = True
            print("Slash commands synchronized")

    async def on_connect(self):
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f'{PRESENCE_MESSAGE}'))
        self.admin = await self.fetch_user(int(ADMIN_ID))

    async def on_guild_join(self, guild):
        if self.admin is None:
            return
        url=f'https://discordbotlist.com/api/v1/bots/{STATS_ID}/stats'
        headers = {
            "Authorization": STATS_TOKEN,
            "Content-Type": 'application/json'
        }
        payload = json.dumps({
            "guilds": len(self.guilds)
        })
        requests.request("POST", url, headers=headers, data=payload)

        notify_me = f'MoveBot was added to {guild.name} ({guild.member_count} members)! Currently in {len(self.guilds)} servers.'
        await self.admin.send(notify_me)

    async def on_guild_remove(self, guild):
        if self.admin is None:
            return
        url=f'https://discordbotlist.com/api/v1/bots/{STATS_ID}/stats'
        headers = {
            "Authorization": STATS_TOKEN,
            "Content-Type": 'application/json'
        }
        payload = json.dumps({
            "guilds": len(self.guilds)
        })
        requests.request("POST", url, headers=headers, data=payload)

        notify_me = f'MoveBot was removed from {guild.name} ({guild.member_count} members)! Currently in {len(self.guilds)} servers.'
        await self.admin.send(notify_me)

move_bot = movebot()

@move_bot.tree.command()
async def help(interaction: discord.Interaction, preference: Optional[Literal[tuple(k for k in available_prefs.keys())]]):
    '''Display help about a preference or send general help in DM.

    Parameters
    ----------
    preference: Optional[Literal[tuple(k for k in available_prefs.keys())]]
        preference to get help about
    '''
    if preference is None:
        e = discord.Embed(title="MoveBot Help")
        e.description = f"""
            This bot can move messages in two different ways.
            *Moving messages requires to have the 'Manage messages' permission.*

            **Method 1: Using the target message's ID**
            `/move [#targetChannelOrThread] [messageID] [optional multi-move] [optional message]`

            **examples:**
            `/move #general 964656189155737620`
            `/move #general 964656189155737620 #general This message belongs in general.`
            `/move #general 964656189155737620 +2 This message and the 2 after it belongs in general.`
            `/move #general 964656189155737620 -3 This message and the 3 before it belongs in general.`
            `/move #general 964656189155737620 ~964656189155737640 This message until 964656189155737640 belongs in general.`

            **Method 2: Contextual menu on target message**
            Right-click on the message, select `Application`>`Move`. Select a target channel or thread.
            Click on `Move` to move only this message, or click on `More options` to select more messages and/or add a notification message.
            {pref_help_description}

            You can reset preferences to default using `/pref reset`.
            **Head over to https://discord.gg/t5N754rmC6 for any questions or suggestions!**"
        """
        await interaction.user.send(embed=e)
        await interaction.response.send_message('Help has been sent in DM.')
    else:
        title = 'Preference Help'
        response_msg = pref_help[preference]
        e = discord.Embed(title=title)
        e.description = response_msg
        await interaction.response.send_message(embed=e)

@move_bot.group_pref.command(name='reset')
async def reset(interaction: discord.Interaction):
    '''Reset all preferences to default'''
    if interaction.guild_id in prefs:
        prefs.pop(interaction.guild_id)
    await reset_prefs(int(interaction.guild_id))
    await interaction.response.send_message("All preferences reset to default")

@move_bot.group_pref.command(name='get')
async def get_pref(interaction: discord.Interaction, preference: Literal[tuple(k for k in available_prefs.keys())]):
    '''Get preferences

    Parameters
    ----------
    preference: Literal[tuple(k for k in available_prefs.keys())]
        preference to get
    '''
    title = "Current Preference"
    response_msg = f"`{preference}`: `{await _get_pref(interaction.guild_id, preference)}`"
    e = discord.Embed(title=title)
    e.description = response_msg
    await interaction.response.send_message(embed=e)

@move_bot.group_pref.command(name='list')
async def list_pref(interaction: discord.Interaction):
    '''List available preferences'''
    title = "Preference Help"
    response_msg = pref_help_description
    e = discord.Embed(title=title)
    e.description = response_msg
    await interaction.response.send_message(embed=e)

@move_bot.group_pref.command(name='set')
async def set_pref(interaction: discord.Interaction, preference: Literal[tuple(k for k in available_prefs.keys())], value: str):
    '''Set preferences

    Parameters
    ----------
    preference: Literal[tuple(k for k in available_prefs.keys())]
        preference to set
    value: str
        new value for the preference
    '''
    if preference == 'move_message':
        await update_move_msg_pref(interaction.guild_id, value)
    else:
        await update_pref(interaction.guild_id, preference, value)
    title = "Preference Updated"
    response_msg = f"**Preference:** `{preference}` Updated to `{value}`"
    e = discord.Embed(title=title)
    e.description = response_msg
    await interaction.response.send_message(embed=e)


@move_bot.tree.command()
@app_commands.checks.has_permissions(manage_messages=True)
async def move(interaction: discord.Interaction, channel: str, msg_id: str, multi_move: Optional[str], notification_message: Optional[str]):
    '''Move a message

    Parameters
    ----------
    channel: str
        new location for moved messages
    msg_id: str
        id of the message to move 
    multi_move: Optional[str] 
        move more than one message. e.g.: +2 / -3 / ~964656189155737640
    notification_message: Optional[str]
        message explaining the reason of the move
    '''
    return await _move(interaction=interaction, channel=channel, msg_id=msg_id, multi_move=multi_move, notification_message=notification_message)

async def _move(interaction: discord.Interaction, channel: str, msg_id: str, multi_move: Optional[str], notification_message: Optional[str]):
    await interaction.response.defer(ephemeral=True)
    # retrieve moved message
    try:
        moved_msg = await interaction.channel.fetch_message(msg_id)
    except:
        return await interaction.followup.send('An invalid message ID was provided. You can ignore the message ID by executing the **move** command as a reply to the target message')

    before_messages = []
    after_messages = []
    # retrieve other messages to be moved
    if multi_move and multi_move.startswith(('+', '-', '~')):
        value = int(multi_move[1:]) # number of messages, or last message id
        if multi_move[0] == '-':
            before_messages = [m async for m in interaction.channel.history(limit=value, before=moved_msg)]
            before_messages.reverse()
        elif multi_move[0] == '+':
            after_messages = [m async for m in interaction.channel.history(limit=value, after=moved_msg)]
        elif multi_move[0] == '~':
            try:
                await interaction.channel.fetch_message(value)
            except:
                return await interaction.followup.send('An invalid destination message ID was provided.')

            limit = int(MAX_MESSAGES)
            found = False
            cursor = moved_msg
            while not found:
                test_messages = [m async for m in interaction.channel.history(limit=limit, after=cursor)]
                if (test_messages[-1].id == interaction.channel.last_message_id) and test_messages[-1].id != value:
                    return await interaction.followup.send('Reached the latest message without finding the destination message ID.')
                for i, msg in enumerate(test_messages):
                    if msg.id == value:
                        after_messages = test_messages[:i+1]
                        found = True
                        break
                if not found:
                    after_messages.extend(test_messages)
                    cursor = test_messages[-1]
        else:
            return await interaction.followup.send('multi_move must start with `-`, `+`, or `~`')

    try:
        target_channel = interaction.guild.get_channel_or_thread(int(channel.strip('<#').strip('>')))
    except:
        return await interaction.followup.send("An invalid channel or thread was provided.")

    wb = None
    wbhks = await interaction.guild.webhooks()
    for wbhk in wbhks:
        if wbhk.name == f'MoveBot-{BOT_ID}':
            wb = wbhk

    parent_channel = target_channel.parent if isinstance(target_channel, Thread) else target_channel
    if wb is None:
        wb = await parent_channel.create_webhook(name=f'MoveBot-{BOT_ID}', reason='Required webhook for MoveBot to function.')
    else:
        if wb.channel != parent_channel:
            await wb.edit(channel=parent_channel)
    if moved_msg.reactions:
        global reactionss
        reactionss = moved_msg.reactions

    author_map = {}
    strip_ping = await _get_pref(interaction.guild_id, "strip_ping")
    for msg in itertools.chain(before_messages, [moved_msg], after_messages):
        msg_content = msg.content.replace('@', '@\u200b') if strip_ping == "1" and '@' in msg.content else msg.content
        files = []
        for file in msg.attachments:
            f = io.BytesIO()
            await file.save(f)
            files.append(discord.File(f, filename=file.filename))

        if isinstance(target_channel, Thread):
            sm = await wb.send(content=msg_content, username=msg.author.display_name, avatar_url=msg.author.avatar, embeds=msg.embeds, files=files, thread=target_channel, wait=True)
            if moved_msg.reactions:
                for r in reactionss:
                    if not isinstance(r.emoji, discord.PartialEmoji):
                        await sm.add_reaction(r.emoji)

        else:
            sm = await wb.send(content=msg_content, username=msg.author.display_name, avatar_url=msg.author.avatar, embeds=msg.embeds, files=files, wait=True)
            if moved_msg.reactions:
                for r in reactionss:
                    if not isinstance(r.emoji, discord.PartialEmoji):
                        await sm.add_reaction(r.emoji)

        if msg.author.id not in author_map:
            author_map[msg.author.id] = msg.author

    notify_dm = await _get_pref(interaction.guild_id, "notify_dm")
    authors = [author_map[a] for a in author_map]
    author_ids = [f"<@!{a.id}>" for a in authors]
    send_objs = []
    if notify_dm == "1":
        send_objs = authors
    elif notify_dm != "2":
        send_objs = [interaction.channel]
    if send_objs:
        for send_obj in send_objs:
            if notify_dm == "1":
                message_users = f"<@!{send_obj.id}>"
            elif len(author_ids) == 1:
                message_users = author_ids[0]
            else:
                message_users = f'{", ".join(author_ids[:-1])}{"," if len(author_ids) > 2 else ""} and {author_ids[-1]}'
            description = await _get_pref(interaction.guild_id, "move_message")
            description = description.replace("MESSAGE_USER", message_users) \
                .replace("DESTINATION_CHANNEL", channel) \
                .replace("MOVER_USER", f"<@!{interaction.user.id}>")
            description = f'{description}: {notification_message or ""}'
            embed = await _get_pref(interaction.guild_id, "embed_message")
            if embed == "1":
                e = discord.Embed(title="Message Moved")
                e.description = description
                await send_obj.send(embed=e)
            else:
                try:
                    await send_obj.send(description)
                except:
                    print("Notification failed")
        delete_original = await _get_pref(interaction.guild_id, "delete_original")
        if delete_original == "1": #This will now only delete messages if the user wants it deleted @SadPuppies 4/9/23
            for msg in itertools.chain(before_messages, [moved_msg], after_messages):
                try: #Also lets print exceptions when they arise
                    await msg.delete()
                except "Missing Access":
                    e = discord.Embed(title="Missing Access", description="The bot cannot access that channel. Please check the permissions (just apply **Admin** to the bot or it's role for EasyMode) or hop into the help server https://discord.gg/msV7r3XPtm for support from the community or devs")
                    await send_obj.send(embed=e)
                except "Unknown Message":
                    e = discord.Embed(title="Unknown Message", description="The bot attempted to delete a message, but could not find it. Did someone already delete it? Was it a part ot a `/move +/-**x** #\channel` command? Hop into the help server https://discord.gg/msV7r3XPtm for support from the community and devs")
                    await send_obj.send(embed=e)
    return await interaction.followup.send(content="Move operation completed", ephemeral=True)


class MovebotView(discord.ui.View):
    def __init__(self, message):
        super().__init__()
        self.channel = None
        self.message = message

    @discord.ui.select(cls=discord.ui.ChannelSelect, min_values=1, max_values=1, placeholder="Destination Channel/Thread", channel_types=[discord.ChannelType.text, discord.ChannelType.private, discord.ChannelType.news, discord.ChannelType.news_thread, discord.ChannelType.public_thread, discord.ChannelType.private_thread])
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.channel = select.values[0].mention
        return await interaction.response.defer()

    @discord.ui.button(label='Move', style=discord.ButtonStyle.red)
    async def move(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.channel is None:
            return await interaction.response.defer()
        self.stop()
        await _move(interaction=interaction, channel=self.channel, msg_id=self.message, multi_move=None, notification_message=None)

    @discord.ui.button(label='More options', style=discord.ButtonStyle.grey)
    async def select_more(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.channel is None:
            return await interaction.response.defer()
        self.stop()
        return await interaction.response.send_modal(MoveBotModal(self.message, self.channel))

class MoveBotModal(discord.ui.Modal, title="More options"):
    def __init__(self, message, channel):
        super().__init__()
        self.channel = channel
        self.message = message

    multi = discord.ui.TextInput(
            label='Select more messages (optional)',
            placeholder='e.g.: +2 / -3 / ~964656189155737640',
            required=False,
            )
    notif = discord.ui.TextInput(
            label='Add a notification message (optional)',
            placeholder='This message until 964656189155737640 belongs in general.',
            required=False,
            )


    async def on_submit(self, interaction: discord.Interaction):
        await _move(interaction=interaction, channel=self.channel, msg_id=self.message, multi_move=self.multi.value, notification_message=self.notif.value)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Something went wrong.', ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)

@move_bot.tree.context_menu(name='Move')
@app_commands.checks.has_permissions(manage_messages=True)
async def move_from_context_menu(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.send_message('Select a destination channel:', view=MovebotView(message.id), ephemeral=True)

move_bot.run(TOKEN)
