#!/usr/bin/python3
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
import json
import discord
import requests
import asqlite # using asqlite now since it is asynchronous
import asyncio # needed for sleep functions
from contextlib import closing
from discord import Thread
from discord.ext import commands # this upgrades from `client` to `bot` (per Rapptz's recommendation)
from dotenv import load_dotenv # this keeps the api_token secret, and also allows for user configs
import logging # pipe all of the output to a log file to make reading through it easier

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
LISTEN_TO = os.getenv('LISTEN_TO')
ADMIN_ID = os.getenv('ADMIN_UID')
BOT_ID = os.getenv('MOVEBOT_ID')
DB_PATH = os.getenv('DB_PATH')
DELETE_ORIGINAL = os.getenv('DELETE_ORIGINAL')
MAX_MESSAGES = os.getenv('MAX_MESSAGES')

available_prefs = {
    "notify_dm": "0",
    "embed_message": "0",
    "move_message": "MESSAGE_USER, your message has been moved to DESTINATION_CHANNEL by MOVER_USER",
    "mod_log_message": "Moved MESSAGE_COUNT messages from SOURCE_CHANNEL to DESTINATION_CHANNEL, ordered by MOVER_USER",
    "strip_ping": "0",
    "delete_original": "1" # allows to original message to be preserved @SadPuppies 5/31/23
}
pref_help = {
    "notify_dm": """
**name:** `notify_dm`
**value:**
 `0`  Sends move message in channel and #mod-log
 `1`  Sends move message as a DM and to #mod-log
 `2`  Sends move message only to #mod-log

**example:**
`!mv pref notify_dm 1`
    """,
    "embed_message": """

**name:** `embed_message`
**value:**
 `0`  Does not embed move message
 `1`  Embeds move message

**example:**
`!mv pref embed_message 1`
    """,
    "move_message": """

**name:** `move_message`
**value:** main message sent to the user.
**variables:** `MESSAGE_USER`, `DESTINATION_CHANNEL`, `MOVER_USER`

**example:**
`!mv pref send_message MESSAGE_USER, your message belongs in DESTINATION_CHANNEL and was moved by MOVER_USER`""",

    "strip_ping": """
**name:** `strip_ping`
**value:**
`0` Do not strip pings
`1` Strip 'everyone' and 'here' pings

**example:**
`!mv pref strip_ping 1`
    """,
    #`delete_original` added to allow users to merely copy @SadPuppies 4/9/23
    "delete_original": """
**name:** `delete_original`
**value:**
`0` Do not delete the original (basically turns the bot into CopyBot)
`1` Deletes the original message (the default functionality)

**example:**
`!mv pref delete_original 0`
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
            #setting some of these values to `INT` type will be tedious at best becuase `move_message` will have to be `TEXT` and specifying different types within a single `update pref` function (see below) is beyond this author's expertise @SadPuppies 4/9/23
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

async def get_pref(guild_id, pref):
    return prefs[guild_id][pref] if guild_id in prefs and pref in prefs[guild_id] else available_prefs[pref]

async def update_pref(guild_id, pref, value): #This needs to be it's own function so that it can be `async`
    if guild_id not in prefs:
        prefs[guild_id] = {"notify_dm": 0, "embed_message": 0, "move_message": "", "strip_ping": 0, "delete_original": 1}
        prefs[guild_id][pref] = value
        async with asqlite.connect(DB_PATH) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(f"INSERT OR IGNORE INTO prefs VALUES (?, ?, ?, ?, ?, ?)", (int(guild_id),prefs[guild_id]["notify_dm"], prefs[guild_id]["embed_message"], prefs[guild_id
]["move_message"], prefs[guild_id]["strip_ping"], prefs[guild_id]["delete_original"]))
                await cursor.close()
                await connection.commit()
    else:
        async with asqlite.connect(DB_PATH) as connection:
            async with connection.cursor() as cursor:
                sql = f"UPDATE prefs SET {pref} = {value} WHERE guild_id = {int(guild_id)}"
                await cursor.execute(sql)
                await cursor.close()
                await connection.commit()

async def update_move_msg_pref(guild_id, moved_message):
    mm = ""
    for word in moved_message:
        mm += word
    prefs[guild_id]["move_message"] = mm
    if guild_id not in prefs:
        prefs[guild_id] = []
        prefs[guild_id][pref] = value
        async with asqlite.connect(DB_PATH) as connection:
            async with connection.cursor() as cursor:
                sql = f"UPDATE prefs SET move_message = {mm} where guild_id = {int(guild_id)}"
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

pref_help_description = """
**Preferences**
You can set bot preferences like so:
`!mv pref [preference name] [preference value]`
"""
for k, v in pref_help.items():
    pref_help_description = pref_help_description + v

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.AutoShardedBot(command_prefix='!', intents=intents, max_messages=int(MAX_MESSAGES)) #upgrading to `bot` because it has been preferred for several months. Using `AutoShardedBot` because we are in too many guilds for regular `Bot`. I had been using `max_messages` previously, I think it saves small bandwidth for the bot, and also increases speed when a command is issued. 10,000 messages had a negligible impact @SadPuppies 4/9/23

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f'for spoilers | {LISTEN_TO} help'))

@bot.event
async def on_guild_join(guild):
    url=f'https://discordbotlist.com/api/v1/bots/{STATS_ID}/stats'
    headers = {
        "Authorization": STATS_TOKEN,
        "Content-Type": 'application/json'
    }
    payload = json.dumps({
        "guilds": len(bot.guilds)
    })
    requests.request("POST", url, headers=headers, data=payload)

    notify_me = f'MoveBot was added to {guild.name} ({guild.member_count} members)! Currently in {len(bot.guilds)} servers.'
    await admin.send(notify_me)
    print(f"Bot has joined a guild. Now in {len(bot.guilds)} guilds.\n")

@bot.event
async def on_guild_remove(guild):
    url=f'https://discordbotlist.com/api/v1/bots/{STATS_ID}/stats'
    headers = {
        "Authorization": STATS_TOKEN,
        "Content-Type": 'application/json'
    }
    payload = json.dumps({
        "guilds": len(bot.guilds)
    })
    requests.request("POST", url, headers=headers, data=payload)

    notify_me = f'MoveBot was removed from {guild.name} ({guild.member_count} members)! Currently in {len(bot.guilds)} servers.'
    await admin.send(notify_me)
    print(f"Bot has left a guild. Now in {len(bot.guilds)} guilds.\n")
    
@bot.event
async def on_message(msg_in):
    if msg_in.author == bot.user or msg_in.author.bot \
            or not msg_in.content.startswith(LISTEN_TO) \
            or not msg_in.author.guild_permissions.manage_messages \
            or not msg_in.author.id == int(ADMIN_ID):
        return

    guild_id = msg_in.guild.id
    txt_channel = msg_in.channel
    is_reply = msg_in.reference is not None
    params = msg_in.content.split(maxsplit=2 if is_reply else 3)

    # !mv help
    if len(params) < 2 or params[1] == 'help':
        e = discord.Embed(title="MoveBot Help")
        e.description = f"""
            This bot can move messages in two different ways.
            *Moving messages requires to have the 'Manage messages' permission.*

            **Method 1: Using the target message's ID**
            `!mv [messageID] [optional multi-move] [#targetChannelOrThread] [optional message]`

            **examples:**
            `!mv 964656189155737620 #general`
            `!mv 964656189155737620 #general This message belongs in general.`
            `!mv 964656189155737620 +2 #general This message and the 2 after it belongs in general.`
            `!mv 964656189155737620 -3 #general This message and the 3 before it belongs in general.`
            `!mv 964656189155737620 ~964656189155737640 #general This message until 964656189155737640 belongs in general.`

            **Method 2: Replying to the target message**
            `!mv [optional multi-move] [#targetChannelOrThread] [optional message]`

            **examples:**
            `!mv #general`
            `!mv #general This message belongs in general.`
            `!mv +2 #general This message and the 2 after it belongs in general.`
            `!mv -3 #general This message and the 3 before it belongs in general.`
            `!mv ~964656189155737640 #general This message until 964656189155737640 belongs in general.`

            {pref_help_description}
            **Head over to https://discord.gg/t5N754rmC6 for any questions or suggestions!**"
        """
        await msg_in.author.send(embed=e)

    # !mv reset
    elif params[1] == "reset":
        if guild_id in prefs:
            prefs.pop(guild_id)
        await reset_prefs(int(guild_id))
        await txt_channel.send("All preferences reset to default")

    # !mv pref [pref_name] [pref_value]
    elif params[1] == "pref":
        title = "Preference Help"
        if len(params) == 2 or params[2] == "?":
            response_msg = pref_help_description
        elif len(params) > 2 and params[2] not in available_prefs:
            title = "Invalid Preference"
            response_msg = f"An invalid preference name was provided.\n{pref_help_description}"
        elif len(params) == 3:
            title = "Current Preference"
            response_msg = f"`{params[2]}`: `{await get_pref(guild_id, params[2])}`"
        elif params[3] == "?":
            response_msg = pref_help[params[2]]
        elif params[2] == "move_message":
            title = "Move Message Updated"
            response_msg = f"**Preference:** `move_message` was updated"
            await update_move_msg_pref(guild_id, params[2:])
        else:
            await update_pref(int(guild_id), params[2], params[3])
            title = "Preferences Updated"
            response_msg = f"**Preference:** `{params[2]}` Updated to `{params[3]}`"
        e = discord.Embed(title=title)
        e.description = response_msg
        await txt_channel.send(embed=e)

    # !mv [msgID] [optional multi-move] [#channel] [optional message]
    else:

        try:
            moved_msg = await txt_channel.fetch_message(msg_in.reference.message_id if is_reply else params[1])
        except:
            await txt_channel.send('An invalid message ID was provided. You can ignore the message ID by executing the **move** command as a reply to the target message')
            return

        channel_param = 1 if is_reply else 2
        before_messages = []
        after_messages = []
        if params[channel_param].startswith(('+', '-', '~')):
            value = int(params[channel_param][1:])
            if params[channel_param][0] == '-':
                before_messages = [m async for m in txt_channel.history(limit=value, before=moved_msg)]
                before_messages.reverse()
            elif params[channel_param][0] == '+':
                after_messages = [m async for m in txt_channel.history(limit=value, after=moved_msg)]
            else:
                try:
                    await txt_channel.fetch_message(value)
                except:
                    await txt_channel.send('An invalid destination message ID was provided.')
                    return

                limit = int(MAX_MESSAGES)
                while True:
                    found = False
                    test_messages = [m async for m in txt_channel.history(limit=limit, after=moved_msg)]
                    for i, msg in enumerate(test_messages):
                        if msg.id == value:
                            after_messages = test_messages[:i+1]
                            found = True
                            break
                        elif msg.id == txt_channel.last_message.id:
                            await txt_channel.send('Reached the latest message without finding the destination message ID.')
                            return
                    if found:
                        break
                    limit += 100

            channel_param += 1
            leftovers = params[channel_param].split(maxsplit=1)
            dest_channel = leftovers[0]
            extra_message = f'\n\n{leftovers[1]}' if len(leftovers) > 1 else ''
        else:
            dest_channel = params[channel_param]
            extra_message = f'\n\n{params[channel_param + 1]}' if len(params) > channel_param + 1 else ''

        try:
            target_channel = msg_in.guild.get_channel_or_thread(int(dest_channel.strip('<#').strip('>')))
        except:
            await txt_channel.send("An invalid channel or thread was provided.")
            return

        wb = None
        wbhks = await msg_in.guild.webhooks()
        for wbhk in wbhks:
            if wbhk.name == 'MoveBot':
                wb = wbhk

        parent_channel = target_channel.parent if isinstance(target_channel, Thread) else target_channel
        if wb is None:
            wb = await parent_channel.create_webhook(name='MoveBot', reason='Required webhook for MoveBot to function.')
        else:
            if wb.channel != parent_channel:
                await wb.edit(channel=parent_channel)
        if moved_msg.reactions:
            global reactionss
            reactionss = moved_msg.reactions

        author_map = {}
        strip_ping = await get_pref(guild_id, "strip_ping")
        moved = 0
        guild = None
        for msg in before_messages + [moved_msg] + after_messages:
            if guild is None:
                guild = msg.guild
            msg_content = msg.content.replace('@', '@\u200b') if strip_ping == "1" and '@' in msg.content else msg.content
            if not msg_content:
                msg_content = '**Empty message. Probably a pin or other channel action.**'
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

            moved = moved + 1

        notify_dm = await get_pref(guild_id, "notify_dm")
        notify_dm = int(notify_dm)
        authors = [author_map[a] for a in author_map]
        author_ids = [f"<@!{a.id}>" for a in authors]
        send_objs = []
        if notify_dm == 1:
            send_objs = authors
        elif notify_dm != 2:
            send_objs = [txt_channel]
        if notify_dm != 2:
            for send_obj in send_objs:
                if notify_dm == 1:
                    message_users = f"<@!{send_obj.id}>"
                elif len(author_ids) == 1:
                    message_users = author_ids[0]
                else:
                    message_users = f'{", ".join(author_ids[:-1])}{"," if len(author_ids) > 2 else ""} and {author_ids[-1]}'
                description = await get_pref(guild_id, "move_message")
                description = description.replace("MESSAGE_USER", message_users) \
                    .replace("DESTINATION_CHANNEL", dest_channel) \
                    .replace("MOVER_USER", f"<@!{msg_in.author.id}>")
                description = f'{description}{extra_message}'
                embed = await get_pref(guild_id, "embed_message")
                if embed == "1":
                    e = discord.Embed(title="Message Moved")
                    e.description = description
                    await send_obj.send(embed=e)
                elif description:
                    await send_obj.send(description)

        mod_channel = discord.utils.get(guild.channels, name="mod-log")
        description = await get_pref(guild_id, "mod_log_message")
        description = description.replace("MESSAGE_COUNT", str(moved)) \
                    .replace("SOURCE_CHANNEL", f"<#{txt_channel.id}>") \
                    .replace("DESTINATION_CHANNEL", dest_channel) \
                    .replace("MOVER_USER", f"`{msg_in.author.name}`")
        try:
            await mod_channel.send(description)
        except "Missing Access":
            e = discord.Embed(title="Missing Access", description="The bot cannot access the mod_log channel. Please check the permissions (just apply **Admin** to the bot or it's role for EasyMode)")
            await txt_channel.send(embed=e)
            
        delete_original = await get_pref(guild_id, "delete_original")
        delete_original = int(delete_original)
        if delete_original == 1: #This will now only delete messages if the user wants it deleted @SadPuppies 4/9/23
            for msg in before_messages + [moved_msg, msg_in] + after_messages:
                try: #Also lets print exceptions when they arise
                    await msg.delete()
                except "Missing Access":
                    e = discord.Embed(title="Missing Access", description="The bot cannot access that channel. Please check the permissions (just apply **Admin** to the bot or it's role for EasyMode)")
                    await txt_channel.send(embed=e)
                except "Unknown Message":
                    e = discord.Embed(title="Unknown Message", description="The bot attempted to delete a message, but could not find it. Did someone already delete it? Was it a part ot a `!mv +/-**x** #\channel` command?")
                    await txt_channel.send(embed=e)
                    
#end
bot.run(TOKEN)
