#!/usr/bin/env python3
########################################
#
# MoveBot modified for Swizzle6
# Create by @Nexas#6792 (221132862567612417)
# Database functions added by @Sojhiro#2008 (206797306173849600)
# More functionality and hosting provided by @SadPuppies | beta<at>timpi.io#7339 (948208421054865410)
# Bug fixes and more functionality from @UnorderedSigh (1037106141668331532)
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
import datetime
import random
import asyncio
import copy
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
STATS_TOKEN = os.getenv('STATS_TOKEN', '')
STATS_ID = os.getenv('MOVEBOT_STATS_ID', 0)
LISTEN_TO = os.getenv('LISTEN_TO')
ADMIN_ID = os.getenv('ADMIN_UID')
BOT_ID = os.getenv('MOVEBOT_ID')
DB_PATH = os.getenv('DB_PATH')
MAX_MESSAGES = int(os.getenv('MAX_MESSAGES', '100'))
DEBUG_MODE = os.getenv('DEBUG_MODE', '1')
BULK_DELETE_MAX_AGE = 24*3600*float(os.getenv('BULK_DELETE_MAX_AGE', '13.9'))
SEND_SLEEP_TIME = float(os.getenv('SEND_SLEEP_TIME', '2.0'))
DELETE_SLEEP_TIME = float(os.getenv('DELETE_SLEEP_TIME', '0.5'))
FETCH_SLEEP_TIME = float(os.getenv('FETCH_SLEEP_TIME', '0.02'))
FETCH_BLOCK = 35 # Maximum number of messages to fetch at a time using 12345 ~67890 syntax
MAX_DELETE = 35 # How many messages to delete at a time in bulk deletion
MAX_SPECIAL_MESSAGES = 20 # Number of messages that may be generated, in addition to copied/moved messages

if LISTEN_TO.rstrip() == LISTEN_TO:
    LISTEN_TO += " "

available_prefs = {
    "notify_dm": "0",
    "embed_message": "0",
    "move_message": "MESSAGE_USER, your message has been LC_OPERATION to DESTINATION_CHANNEL by MOVER_USER.",
    "strip_ping": "0",
    "delete_original": "1" # allows to original message to be preserved @SadPuppies 5/31/23
}
pref_help = {
    "notify_dm": f"""
**name:** `notify_dm`
**value:**
 `0`  Sends move message in channel and #mod-log
 `1`  Sends move message as a DM and to #mod-log
 `2`  Sends move message only to #mod-log

**example:**
`{LISTEN_TO}pref notify_dm 1`
    """,
    "embed_message": """

**name:** `embed_message`
**value:**
 `0`  Does not embed move message
 `1`  Embeds move message

**example:**
`{LISTEN_TO}pref embed_message 1`
    """,
    "move_message": """

**name:** `move_message`
**value:** main message sent to the user.
**variables:** `MESSAGE_USER`, `DESTINATION_CHANNEL`, `MOVER_USER`

**example:**
`{LISTEN_TO}pref send_message MESSAGE_USER, your message belongs in DESTINATION_CHANNEL and was moved by MOVER_USER`""",

    "strip_ping": """
**name:** `strip_ping`
**value:**
`0` Do not strip pings
`1` Strip 'everyone' and 'here' pings

**example:**
`{LISTEN_TO}pref strip_ping 1`
    """,
    #`delete_original` added to allow users to merely copy @SadPuppies 4/9/23
    "delete_original": f"""
**name:** `delete_original`
**value:**
`0` Do not delete the original (basically turns the bot into CopyBot)
`1` Deletes the original message (the default functionality)

**example:**
`{LISTEN_TO}pref delete_original 0`
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

async def get_pref(guild_id, pref, override):
    if pref in override:
        return override[pref]
    result = prefs[guild_id][pref] if guild_id in prefs and pref in prefs[guild_id] else available_prefs[pref]
    if type(result) == list or type(result) == tuple:
        return result[0]
    elif result is None:
        return 0
    else:
        return result

async def update_pref(guild_id, pref, value): #This needs to be it's own function so that it can be `async`
    if guild_id not in prefs:
        prefs[guild_id] = copy.deepcopy(available_prefs)
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

async def send_error(send_obj, exception, title, details):
    e = discord.Embed(title = title, description = details)
    if DEBUG_MODE and exception:
        e.description += "\n" + "Discord error message: " + str(exception)
    await send_obj.send(embed=e)

async def send_mod_log(send_obj, message):
    try:
        await send_obj.send(message)
    except Exception as exc:
        await send_error(send_obj, exc, "Moderation log inaccessible",
                   "Unable to log a moderation action.")

def split_pair(arg):
    result = arg.split(maxsplit = 1)
    if not result:
        return '', ''
    elif len(result) == 1:
        return result[0], ''
    return result

def parse_args(arg, maxsplit):
    this, rest = split_pair(arg)
    if not arg:
        return [''], {}
    args = [this]
    opts = set()
    while rest and len(args)<maxsplit:
        this, rest = split_pair(rest)
        
        if this and this[0] == '/':
            opts.add(this)
        else:
            args.append(this)
    if len(args)<=maxsplit and rest:
        args.append(rest)
    return args, opts

async def make_prefs_from(send_obj, opts):
    invalid = set()
    override = dict()
    for opt in opts:
        if   opt == '/mention':    override['notify_dm'] = 0
        elif opt == '/dm':         override['notify_dm'] = 1
        elif opt == '/silent':     override['notify_dm'] = 2
        elif opt == '/no-embed':   override['embed_message'] = 0
        elif opt == '/embed':      override['embed_message'] = 1
        elif opt == '/no-strip':   override['strip_ping'] = 0
        elif opt == '/strip':      override['strip_ping'] = 1
        elif opt == '/keep':       override['delete_original'] = 0
        elif opt == '/no-delete':  override['delete_original'] = 0
        elif opt == '/delete':     override['delete_original'] = 1
        else:
            invalid.add(opt)
    if invalid:
        invalids = ", ".join(sorted(invalid))
        s = 's' if len(invalid) > 1 else ''
        await send_error(send_obj, None, "Invalid option", f"Ignoring unrecognized option{s}: {invalids}")
    return override

pref_help_description = f"""
**Preferences**
You can set bot preferences like so:
`{LISTEN_TO}pref [preference name] [preference value]`
"""
for k, v in pref_help.items():
    pref_help_description = pref_help_description + v

help_description = f"""
    This bot can move messages in two different ways.
    *Moving messages requires to have the 'Manage messages' permission in the source and destination channels.*

    **Method 1: Using the target message's ID**
    `{LISTEN_TO}[messageID] [optional multi-move] [#targetChannelOrThread] [optional message]`

    **examples:**
    `{LISTEN_TO}964656189155737620 #general`
    `{LISTEN_TO}964656189155737620 #general This message belongs in general.`
    `{LISTEN_TO}964656189155737620 +2 #general This message and the 2 after it belongs in general.`
    `{LISTEN_TO}964656189155737620 -3 #general This message and the 3 before it belongs in general.`
    `{LISTEN_TO}964656189155737620 ~964656189155737640 #general This message until 964656189155737640 belongs in general.`

    **Method 2: Replying to the target message**
    `{LISTEN_TO}[optional multi-move] [#targetChannelOrThread] [optional message]`

    **examples:**
    `{LISTEN_TO}#general`
    `{LISTEN_TO}#general This message belongs in general.`
    `{LISTEN_TO}+2 #general This message and the 2 after it belongs in general.`
    `{LISTEN_TO}-3 #general This message and the 3 before it belongs in general.`
    `{LISTEN_TO}~964656189155737640 #general This message until 964656189155737640 belongs in general.`

    **Options:**
    You specify custom behaviors by putting / options after the `{LISTEN_TO}`. These will override the preferences described below.
    `{LISTEN_TO}/delete` Delete the original messages (ie. move them)
    `{LISTEN_TO}/keep` Do not delete the original messages (ie. act like CopyBot)
    `{LISTEN_TO}/no-delete` Synonym for `{LISTEN_TO}/keep`

    `{LISTEN_TO}/silent` Do not notify users that their message was moved or copied.
    `{LISTEN_TO}/dm` Notify users by direct message.
    `{LISTEN_TO}/mention` Notify users by mentioning them.

    `{LISTEN_TO}/embed` Put the notification in an embedded message. (If notification is enabled.)
    `{LISTEN_TO}/no-embed` Do not put the notification in an embedded message.

    **examples:**
    `{LISTEN_TO}/embed /dm /keep -3 #general Copying this message and the three before it to general; notify users by direct messages in embeds.`
    `{LISTEN_TO}/silent -3 #general Move this message and the three before it to general without notifying users.`
     {pref_help_description}
"""

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.AutoShardedBot(command_prefix='!', intents=intents, max_messages=None) #upgrading to `bot` because it has been preferred for several months. Using `AutoShardedBot` because we are in too many guilds for regular `Bot`. I had been using `max_messages` previously, I think it saves small bandwidth for the bot, and also increases speed when a command is issued. 10,000 messages had a negligible impact @SadPuppies 4/9/23
admin = bot.get_user(ADMIN_ID)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f'for spoilers | {LISTEN_TO} help'))

@bot.event
async def on_guild_join(guild):
    if STATS_ID and STATS_TOKEN:
        url=f'https://discordbotlist.com/api/v1/bots/{STATS_ID}/stats'
        headers = {
            "Authorization": STATS_TOKEN,
            "Content-Type": 'application/json'
        }
        payload = json.dumps({
            "guilds": len(bot.guilds)
        })
        requests.request("POST", url, headers=headers, data=payload)
    if admin:
        notify_me = f'MoveBot was added to {guild.name} ({guild.member_count} members)! Currently in {len(bot.guilds)} servers.'
        await admin.send(notify_me)
        print(f"Bot has joined a guild. Now in {len(bot.guilds)} guilds.\n")

@bot.event
async def on_guild_remove(guild):
    if STATS_ID and STATS_TOKEN:
        url=f'https://discordbotlist.com/api/v1/bots/{STATS_ID}/stats'
        headers = {
            "Authorization": STATS_TOKEN,
            "Content-Type": 'application/json'
        }
        payload = json.dumps({
            "guilds": len(bot.guilds)
        })
        requests.request("POST", url, headers=headers, data=payload)

    if admin:
        notify_me = f'MoveBot was removed from {guild.name} ({guild.member_count} members)! Currently in {len(bot.guilds)} servers.'
        await admin.send(notify_me)
        print(f"Bot has left a guild. Now in {len(bot.guilds)} guilds.\n")

@bot.event
async def on_message(msg_in):
    if not msg_in.content.startswith(LISTEN_TO):
        return

    txt_channel = msg_in.channel
    mod_channel = discord.utils.get(msg_in.guild.channels, name="mod-log")
    if msg_in.author == bot.user or msg_in.author.bot:
        return
    if not txt_channel.permissions_for(msg_in.author).manage_messages:
        send_channel = mod_channel if mod_channel else txt_channel
        await send_channel.send(f"Ignoring command from user <@!{msg_in.author.id}> because they don't have manage_messages permissions on origin channel <#{txt_channel.id}>.")
        return

    guild_id = msg_in.guild.id
    is_reply = msg_in.reference is not None
    params, options = parse_args(msg_in.content, 2 if is_reply else 3)
    override = await make_prefs_from(txt_channel, options)

    # !mv help
    if len(params) < 2 or params[1] == 'help':
        e = discord.Embed(title="MoveBot Help")
        e.description = help_description
        async with msg_in.author.typing():
            await msg_in.author.send(embed=e)
            await delete_messages(msg_in, [msg_in], 1)
        return

    elif params[1] == "ping":
        latency = bot.latency
        bpm = int(round(60.0 / max(1e-9, latency)))
        ms = latency*1000.0
        e = discord.Embed(title="Pong", description=f"Heartbeat: {bpm} BPM ({ms:.1f}ms).")
        await txt_channel.send(embed=e)
        return

    # !mv reset
    elif params[1] == "reset":
        if not msg_in.author.guild_permissions.administrator:
            send_channel = mod_channel if mod_channel else txt_channel
            await send_channel.send(f"Refusing request from <@!{msg_in.author.id}> to reset preferences because they're not an administrator.")
            return
        if guild_id in prefs:
            prefs.pop(guild_id)
        async with msg_in.author.typing():
            await reset_prefs(int(guild_id))
            await txt_channel.send("All preferences reset to default")
            await delete_messages(msg_in, [msg_in], 1)
        return

    # !mv pref [pref_name] [pref_value]
    elif params[1] == "pref":
        title = "Preference Help"
        send_obj = txt_channel
        if len(params) == 2 or params[2] == "?":
            response_msg = pref_help_description
            send_obj = msg_in.author
        elif not msg_in.author.guild_permissions.administrator:
            send_channel = mod_channel if mod_channel else txt_channel
            await send_channel.send(f"Refusing request from <@!{msg_in.author.id}> to change preferences because they're not an administrator.")
            return
        elif len(params) > 2 and params[2] not in available_prefs:
            title = "Invalid Preference"
            response_msg = f"Preference name \"{params[2]}\" is invalid.\nType `{LISTEN_TO}pref ?` for help."
        elif len(params) == 3:
            title = "Current Preference"
            response_msg = f"`{params[2]}`: `{await get_pref(guild_id, params[2], override)}`"
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
        e = discord.Embed(title=title, description = response_msg)
        async with send_obj.typing():
            await send_obj.send(embed=e)
            await delete_messages(msg_in, [msg_in], 1)
        return

    # !mv [msgID] [optional multi-move] [#channel] [optional message]
    async with txt_channel.typing():
        moved_msg = await fetch_moved_message(msg_in, params, is_reply)
        if moved_msg is None:
            return

        ( extra_message, before_messages, after_messages, dest_channel ) = await fetch_other_messages(is_reply, msg_in, params, moved_msg)
        if extra_message is None:
            return

        target_channel = await find_target_channel(msg_in, dest_channel, mod_channel)
        moved, author_map = await copy_messages(before_messages, moved_msg, after_messages, msg_in, target_channel, override)
        delete_original = int(await get_pref(guild_id, "delete_original", override))
        await notify_users(msg_in, override, author_map, dest_channel, delete_original, extra_message)
        mod_channel = await send_to_mod_channel(mod_channel, msg_in, moved, dest_channel, delete_original)
        await delete_messages(msg_in, before_messages + [moved_msg] + after_messages + [msg_in], delete_original)

async def fetch_moved_message(msg_in, params, is_reply):
        txt_channel = msg_in.channel
        try:
            return await txt_channel.fetch_message(msg_in.reference.message_id if is_reply else params[1])
        except Exception as exc:
            await send_error(txt_channel, exc, "Cannot find message",
                              "You can ignore the message ID by executing the **move** command as a reply to the target message.")
            return None

async def fetch_other_messages(is_reply, msg_in, params, moved_msg):
        txt_channel = msg_in.channel
        channel_param = 1 if is_reply else 2
        before_messages = []
        after_messages = []
        if params[channel_param].startswith(('+', '-', '~')):
            value = int(params[channel_param][1:])
            if params[channel_param][0] in '+-' and value > MAX_MESSAGES-1:
                await send_error(txt_channel, None, f'Maximum allowed messages is {MAX_MESSAGES}.')

            if params[channel_param][0] == '-':
                first = True
                async for msg in txt_channel.history(limit=value, before=moved_msg):
                    if not first:
                        await asyncio.sleep(FETCH_SLEEP_TIME)
                    first = False
                    before_messages.append(msg)
                before_messages.reverse()
            elif params[channel_param][0] == '+':
                first = True
                async for msg in txt_channel.history(limit=value, after=moved_msg):
                    if not first:
                        await asyncio.sleep(FETCH_SLEEP_TIME)
                    first = False
                    after_messages.append(msg)
            else:
                logger.info('scan a message range')
                try:
                    await txt_channel.fetch_message(value)
                except Exception as exc:
                    await send_error(txt_channel, exc, "Cannot find message",
                                     'An invalid destination message ID was provided.')
                    return ( None, None, None, None )

                found = False
                first = True
                async for msg in txt_channel.history(limit=MAX_MESSAGES-1, after=moved_msg):
                    if not first:
                        await asyncio.sleep(FETCH_SLEEP_TIME)
                    first = False
                    after_messages.append(msg)
                    found = msg.id == value
                    if found:
                        break
                if not found:
                    await send_error(txt_channel, None, 'Cannot find message',
                                     f'Destination message {value} is not within {MAX_MESSAGES-1} after first message. '
                                     'Try moving fewer messages at a time.')
                    return ( None, None, None, None )

            channel_param += 1
            leftovers = params[channel_param].split(maxsplit=1)
            dest_channel = leftovers[0]
            extra_message = f'\n\n{leftovers[1]}' if len(leftovers) > 1 else ''
        else:
            dest_channel = params[channel_param]
            extra_message = f'\n\n{params[channel_param + 1]}' if len(params) > channel_param + 1 else ''
        return ( extra_message, before_messages, after_messages, dest_channel )

async def find_target_channel(msg_in, dest_channel, mod_channel):
        try:
            target_channel = msg_in.guild.get_channel_or_thread(int(dest_channel.strip('<#').strip('>')))
        except Exception as exc:
            await send_error(txt_channel, exc, "Cannot find channel.", "An invalid channel or thread was provided.")
            return None

        if not target_channel.permissions_for(msg_in.author).manage_messages:
            send_channel = mod_channel if mod_channel else txt_channel
            await send_mod_log(send_channel, f"Ignoring command from user <@!{msg_in.author.id}> because they don't have manage_messages permissions on destination channel <#{target_channel.id}>.")
            return None
        return target_channel

async def copy_messages(before_messages, moved_msg, after_messages, msg_in, target_channel, override):
        webhook_name = f'MoveBot {BOT_ID}'
        logger.info("Find webhook "+webhook_name)
        guild_id = msg_in.guild.id
        wb = None
        wbhks = await msg_in.guild.webhooks()
        for wbhk in wbhks:
            if wbhk.name == webhook_name:
                wb = wbhk

        parent_channel = target_channel.parent if isinstance(target_channel, Thread) else target_channel
        if wb is None:
            logger.info("Create webhook "+webhook_name)
            wb = await parent_channel.create_webhook(name=webhook_name, reason='Required webhook for MoveBot to function.')
        else:
            if wb.channel != parent_channel:
                await wb.edit(channel=parent_channel)
        if moved_msg.reactions:
            global reactionss
            reactionss = moved_msg.reactions

        author_map = {}
        strip_ping = int(await get_pref(guild_id, "strip_ping", override))
        moved = 0
        guild = None
        first = True
        for msg in before_messages + [moved_msg] + after_messages:
            if not first:
                await asyncio.sleep(SEND_SLEEP_TIME)
            first = False
            if guild is None:
                guild = msg.guild
            msg_content = msg.content.replace('@', '@\u200b') if strip_ping == 1 and '@' in msg.content else msg.content
            if not msg_content:
                msg_content = '*(empty message)*'
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
        return ( moved, author_map )

async def send_to_mod_channel(mod_channel, msg_in, moved, dest_channel, delete_original):
        if not mod_channel:
            mod_channel = discord.utils.get(msg_in.guild.channels, name="mod-log")
        if mod_channel:
            txt_channel = msg_in.channel
            description = "CC_OPERATION MESSAGE_COUNT messages from SOURCE_CHANNEL to DESTINATION_CHANNEL, ordered by MOVER_USER."
            description = description.replace("MESSAGE_COUNT", str(moved)) \
                                     .replace("SOURCE_CHANNEL", f"<#{txt_channel.id}>") \
                                     .replace("DESTINATION_CHANNEL", dest_channel) \
                                     .replace("MOVER_USER", f"`{msg_in.author.name}`") \
                                     .replace("LC_OPERATION", 'moved' if delete_original else 'copied') \
                                     .replace("CC_OPERATION", 'Moved' if delete_original else 'Copied')
            await send_mod_log(mod_channel, description)
        return mod_channel

async def notify_users(msg_in, override, author_map, dest_channel, delete_original, extra_message):
        txt_channel = msg_in.channel
        guild_id = msg_in.guild.id
        notify_dm = await get_pref(guild_id, "notify_dm", override)
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
                description = await get_pref(guild_id, "move_message", override)
                description = description.replace("MESSAGE_USER", message_users) \
                    .replace("DESTINATION_CHANNEL", dest_channel) \
                    .replace("MOVER_USER", f"<@!{msg_in.author.id}>") \
                    .replace("LC_OPERATION", 'moved' if delete_original else 'copied') \
                    .replace("CC_OPERATION", 'Moved' if delete_original else 'Copied')
                description = f'{description}{extra_message}'
                embed = int(await get_pref(guild_id, "embed_message", override))
                try:
                    if embed == 1:
                        e = discord.Embed(title="Message Moved")
                        e.description = description
                        await send_obj.send(embed=e)
                    elif description:
                        await send_obj.send(description)
                except (discord.NotFound, commands.errors.MessageNotFound) as exc:
                    pass # Probably trying to DM a MoveBot-generated message

async def delete_messages(msg_in, messages, delete_original): 
        txt_channel = msg_in.channel

        # Split messages into blocks of MAX_DELETE or less for bulk deletion.
        bulk_delete = []

        # Messages too old cannot be bulk deleted. We'll delete them one by one instead.
        one_by_one = []
        
        if delete_original:
            for msg in messages:
                age = (datetime.datetime.now(datetime.timezone.utc) - msg.created_at).total_seconds()
                if age > BULK_DELETE_MAX_AGE:
                    one_by_one.append(msg)
                else:
                    if not bulk_delete or len(bulk_delete[-1]) > MAX_DELETE:
                        bulk_delete.append([])
                    bulk_delete[-1].append(msg)
            # Special case: only one message. Don't use a bulk deletion:
            if len(bulk_delete) == 1 and len(bulk_delete[0]) == 1:
                one_by_one.append(bulk_delete[0][0])
                bulk_delete = []
        else:
            one_by_one = [ msg_in ]

        # Delete messages if desired.
        first = True
        try:
            first = True
            for delete_list in bulk_delete:
                if not first:
                    await asyncio.sleep(DELETE_SLEEP_TIME)
                first = False
                await txt_channel.delete_messages(delete_list)
            for msg in one_by_one:
                if not first:
                    await asyncio.sleep(DELETE_SLEEP_TIME)
                first = False
                await msg.delete()
        except (discord.NotFound, commands.errors.MessageNotFound) as exc:
            await send_error(txt_channel, exc, "Unknown Message",
                             "The bot attempted to delete a message, but could not find it. "
                             "Did someone already delete it? "
                             + f"Was it a part of a `{LISTEN_TO}+/-**x** #\channel` command?")
        except Exception as exc:
            await send_error(txt_channel, exc, "Deletion failed.",
                             "Some messages may not have been deleted. "
                             + "Please check the permissions (just apply **Admin** to the bot or its role for EasyMode)")
            raise
#end
bot.run(TOKEN)
