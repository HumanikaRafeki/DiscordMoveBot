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
import collections
from contextlib import closing
from discord import Thread
from discord.ext import commands # this upgrades from `client` to `bot` (per Rapptz's recommendation)
from dotenv import load_dotenv # this keeps the api_token secret, and also allows for user configs
import logging # pipe all of the output to a log file to make reading through it easier

load_dotenv()

LOG_PATH = os.getenv('LOG_PATH')

logger = logging.getLogger('discord')
trace = logging.getLogger('discord.trace')
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
MAX_FAILED_COPIES = int(os.getenv('MAX_FAILED_COPIES', '10'), 10)
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

# For generating thread names when moving messages to a forum.
some_words = [
"Aero", "Alizarin", "Almond", "Amazon", "Amber", "Amethyst", "Apricot", "Aqua",
"Aquamarine", "Aureolin", "Azure", "Beaver", "Beige", "Bisque", "Bistre",
"Black", "Blue", "Blue-Violet", "Bluetiful", "Blush", "Bole", "Bone", "Bronze",
"Brown", "Buff", "Burgundy", "Burlywood", "Byzantine", "Byzantium", "Camel",
"Canary", "Cardinal", "Carmine", "Carnelian", "Catawba", "Celadon", "Celeste",
"Cerise", "Cerulean", "Champagne", "Charcoal", "Chestnut", "Cinereous",
"Cinnabar", "Citrine", "Citron", "Claret", "Coffee", "Copper", "Coquelicot",
"Coral", "Cordovan", "Corn", "Cornsilk", "Cream", "Crimson", "Cyan",
"Cyclamen", "Dandelion", "Denim", "Desert", "Ebony", "Ecru", "Eggplant",
"Eggshell", "Emerald", "Eminence", "Erin", "Fallow", "Fandango", "Fawn",
"Finn", "Firebrick", "Flame", "Flax", "Flirt", "Frostbite", "Fuchsia",
"Fulvous", "Gainsboro", "Gamboge", "Glaucous", "Goldenrod", "Green",
"Green-Blue", "Gunmetal", "Harlequin", "Heliotrope", "Iceberg", "Inchworm",
"Independence", "Indigo", "Irresistible", "Isabelline", "Ivory", "Jasmine",
"Jet", "Jonquil", "Keppel", "Kobe", "Kobi", "Kobicha", "Lava", "Lemon",
"Nickel", "Nyanza", "Ochre", "Olive", "Olivine", "Onyx", "Opal", "Orange",
"Orange-Red", "Orange-Yellow", "Orchid", "Oxblood", "Parchment", "Patriarch",
"Paua", "Peach", "Pear", "Periwinkle", "Persimmon", "Phlox", "Pink",
"Pistachio", "Platinum", "Plum", "Popstar", "Prune", "Puce", "Pumpkin",
"Purple", "Purpureus", "Rajah", "Raspberry", "Razzmatazz", "Red", "Red-Orange",
"Red-Purple", "Red-Violet", "Redwood", "Rhythm", "Rose", "Rosewood", "Ruber",
"Ruby", "Rufous", "Russet", "Rust", "Saffron", "Sage", "Salmon", "Sand",
"Sapphire", "Scarlet", "Seance", "Seashell", "Secret", "Sepia", "Shadow",
"Sienna", "Silver", "Sinopia", "Skobeloff", "Smitten", "Snow", "Straw",
"Strawberry", "Sunglow", "Sunray", "Sunset", "Tan", "Tangerine", "Taupe",
"Teal", "Technobotanica", "Telemagenta", "Thistle", "Timberwolf", "Tomato",
"Tourmaline", "Tumbleweed", "Turquoise", "Tuscan", "Tuscany", "Ultramarine",
"Umber", "Vanilla", "Verdigris", "Vermilion", "Vermilion", "Veronica",
"Violet", "Violet-Blue", "Violet-Red", "Viridian", "Volt", "Wheat", "White",
"Wine", "Wisteria", "Xanadu", "Xanthic", "Xanthous", "Yellow", "Yellow-Green",
"Zaffre", "Zomp"
]

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
    "embed_message": f"""

**name:** `embed_message`
**value:**
 `0`  Does not embed move message
 `1`  Embeds move message

**example:**
`{LISTEN_TO}pref embed_message 1`
    """,
    "move_message": f"""

**name:** `move_message`
**value:** main message sent to the user.
**variables:** `MESSAGE_USER`, `DESTINATION_CHANNEL`, `MOVER_USER`

**example:**
`{LISTEN_TO}pref send_message MESSAGE_USER, your message belongs in DESTINATION_CHANNEL and was moved by MOVER_USER`""",

    "strip_ping": f"""
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
`2` Also delete messages that MoveBot could not copy.

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

class MoveBotException(Exception):
    def __init__(self,where,operation):
        self.where = str(where)
        self.operation = str(operation)
    def description(self):
        return f'{self.where} said this:\n\t\t{self.operation}\n'

class MoveBotWebhookInUse(MoveBotException): pass
class MoveBotAborted(MoveBotException): pass

class MoveBotWebhookLock:
    guilds=dict()
    def __init__(self,guild_id,where,operation):
        self.guild_id = guild_id
        self.where = str(where)
        self.operation = str(operation)
    def __enter__(self):
        where_op = MoveBotWebhookLock.guilds.get(self.guild_id,None)
        if where_op:
            raise MoveBotWebhookInUse(where_op[0], where_op[1])
        MoveBotWebhookLock.guilds[self.guild_id] = [self.where, self.operation]
    def __exit__(self,a,b,c):
        del MoveBotWebhookLock.guilds[self.guild_id]
        return None

class MoveBotAborter:
    in_use=collections.defaultdict(set)
    def __init__(self,log_channel,guild_id,where,operation):
        self.guild_id = guild_id
        self.where = str(where)
        self.operation = str(operation)
        self.abort_info = None
        self.log_channel = log_channel
    async def __aenter__(self):
        MoveBotAborter.in_use[self.guild_id].add(self)
    async def __aexit__(self,exc_type,exc_value,traceback):
        MoveBotAborter.in_use[self.guild_id].remove(self)
        if exc_type is MoveBotAborted and self.log_channel:
            await send_info(self.log_channel, None, 'Operation Aborted',
                      f'This operation by {self.where}:\n{self.operation}\nwas aborted by request of {exc_value.where}')
            return True
        return False
    def abort(self,where,operation):
        self.abort_info = [where,operation]
    def checkpoint(self):
        if self.abort_info:
            abort_info = self.abort_info
            self.abort_info = None
            raise MoveBotAborted(*abort_info)
    def abort_others(self):
        for movebot in MoveBotAborter.in_use[self.guild_id]:
            if movebot is not self:
                movebot.abort(self.where,self.operation)
    def movebots_in_guild(self):
        return iter(MoveBotAborter.in_use[self.guild_id])

class Sleeper:
    def __init__(self,naptime):
        self.naptime=float(naptime)
        self.slept=False
    def has_slept(self):
        return self.slept
    def get_naptime(self):
        return self.naptime
    async def nap(self):
        await asyncio.sleep(self.naptime)
        self.slept=True

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
        prefs[guild_id][pref] = value
        async with asqlite.connect(DB_PATH) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(f"UPDATE prefs SET {pref} = ? WHERE guild_id = {int(guild_id)}", (value,))
                await cursor.close()
                await connection.commit()

async def reset_prefs(guild_id):
    async with asqlite.connect(DB_PATH) as connection:
        async with connection.cursor() as cursor:
            sql = f"DELETE FROM prefs WHERE guild_id = {int(guild_id)}"
            await cursor.execute(sql)
            await cursor.close()
            await connection.commit()

async def send_info(send_obj, exception, title, details):
    e = discord.Embed(title = title, description = details)
    if DEBUG_MODE and exception:
        description = e.description
        guild = getattr(send_obj,'guild',None)
        description = f'{guild.name}(#{guild.id}): {e.description}' if guild else e.description
        trace.warning(description,exc_info=True)
        e.description += "\n" + "Discord error message: " + str(exception)
    await send_obj.send(embed=e)

async def send_mod_log(send_obj, message):
    try:
        await send_obj.send(message)
    except Exception as exc:
        await send_info(send_obj, exc, "Moderation log inaccessible",
                   "Unable to log a moderation action.")
        raise

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
        elif opt == '/delete-all': override['delete_original'] = 2
        else:
            invalid.add(opt)
    if invalid:
        invalids = ", ".join(sorted(invalid))
        s = 's' if len(invalid) > 1 else ''
        await send_info(send_obj, None, "Invalid option", f"Ignoring unrecognized option{s}: {invalids}")
        raise
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
    *Moving messages requires the 'Manage messages' permission in both source and destination channels. Moving threads requires the 'Create public threads' permission in the destination channel.*

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

    **Method 3: Move all messages in a thread to a new thread**
    `{LISTEN_TO}#sourceThread #targetChannel [optional message]`

    **examples:**
    `{LISTEN_TO}#UglyBabyPictures #general Moves all messages in the #UglyBabyPictures thread to a new thread by that name in #general`

    **Options:**
    You specify custom behaviors by putting / options after the `{LISTEN_TO}`. These will override the preferences described below.
    `{LISTEN_TO}/delete` Delete the original messages (ie. move them)
    `{LISTEN_TO}/delete-all` Also delete messages that couldn't be fully copied.
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
bot = commands.AutoShardedBot(command_prefix=LISTEN_TO[0], intents=intents, max_messages=None) #upgrading to `bot` because it has been preferred for several months. Using `AutoShardedBot` because we are in too many guilds for regular `Bot`. I had been using `max_messages` previously, I think it saves small bandwidth for the bot, and also increases speed when a command is issued. 10,000 messages had a negligible impact @SadPuppies 4/9/23
admin = bot.get_user(ADMIN_ID)
bot_name = 'MoveBot'
if bot.user and bot.user.name:
    bot_name = bot.user.name

async def random_thread_name():
    return ' '.join([ random.choice(some_words) for x in range(2) ]) + ' ' + bot_name

def as_channel_id(text: str):
    if text.startswith('<'):
        return int(text.strip('<#').strip('>'))
    elif text.startswith('#'):
        return int(text.strip('#'))
    else:
        return None


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
        send_channel = mod_channel if mod_channel else msg_in.channel
        await send_channel.send(f"Ignoring command from user <@!{msg_in.author.id}> because they don't have manage_messages permissions on origin channel <#{txt_channel.id}>.")
        await msg_in.add_reaction("🚫")
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
            await msg_in.add_reaction("👍")
        return

    elif params[1] == 'abort':
        await msg_in.add_reaction("⏳")
        await abort_movebot(msg_in)
        await msg_in.add_reaction("👍")
        return

    elif params[1] == "ping":
        latency = bot.latency
        bpm = int(round(60.0 / max(1e-9, latency)))
        ms = latency*1000.0
        e = discord.Embed(title="Pong", description=f"Heartbeat: {bpm} BPM ({ms:.1f}ms).")
        await txt_channel.send(embed=e)
        await msg_in.add_reaction("🏓")
        return

    # !mv reset
    elif params[1] == "reset":
        if guild_id in prefs:
            prefs.pop(guild_id)
        async with msg_in.author.typing():
            await reset_prefs(int(guild_id))
            await txt_channel.send("All preferences reset to default")
            await msg_in.add_reaction("👍")
        return

    # !mv pref [pref_name] [pref_value]
    elif params[1] == "pref":
        title = "Preference Help"
        send_obj = txt_channel
        if len(params) == 2 or params[2] == "?":
            response_msg = pref_help_description
            send_obj = msg_in.author
        elif len(params) > 2 and params[2] not in available_prefs:
            title = "Invalid Preference"
            response_msg = f"Preference name \"{params[2]}\" is invalid.\nType `{LISTEN_TO}pref ?` for help."
        elif len(params) == 3:
            title = "Current Preference"
            response_msg = f"`{params[2]}`: `{await get_pref(guild_id, params[2], override)}`"
        elif params[3] == "?":
            response_msg = pref_help[params[2]]
        elif params[2] == "move_message":
            await update_pref(guild_id, 'move_message', ' '.join(params[3:]))
            title = "Move Message Updated"
            result = await get_pref(guild_id, "move_message", {})
            response_msg = f"**Preference:** `{params[2]}` Updated to `{result}`"
        else:
            await update_pref(int(guild_id), params[2], params[3])
            title = "Preferences Updated"
            result = await get_pref(guild_id, params[2], {})
            response_msg = f"**Preference:** `{params[2]}` Updated to `{result}`"
        e = discord.Embed(title=title, description = response_msg)
        async with send_obj.typing():
            await send_obj.send(embed=e)
            await msg_in.add_reaction("👍")
        return

    # !mv [msgID] [optional multi-move] [#channel] [optional message]
    action = f'<@!{msg_in.author.id}> in <#{msg_in.channel.id}> with {msg_in.jump_url}'
    aborter = MoveBotAborter(msg_in.channel, guild_id, action, msg_in.content)
    await msg_in.add_reaction("⏳")
    async with txt_channel.typing(), aborter:
        assert(aborter)
        moved_msg, source_channel = await fetch_moved_message(msg_in, params, is_reply)
        if moved_msg is None:
            return
        ( extra_message, before_messages, after_messages, dest_channel ) = await fetch_other_messages(aborter, is_reply, msg_in, params, moved_msg, source_channel, mod_channel)
        if extra_message is None:
            return
        target_channel = await find_target_channel(msg_in, dest_channel, mod_channel)
        if target_channel is None:
            return

        make_thread_named = None
        different_target = True
        if source_channel and not isinstance(target_channel, discord.Thread):
            make_thread_named = source_channel.name
        elif isinstance(target_channel, discord.ForumChannel):
            make_thread_named = await random_thread_name()
        else:
            different_target = False

        await msg_in.add_reaction("👥")
        delete_original = int(await get_pref(guild_id, "delete_original", override))
        try:
            with MoveBotWebhookLock(msg_in.guild.id, action, msg_in.content):
                moved, failed, author_map, new_channel = await copy_messages(aborter, before_messages, moved_msg, after_messages, msg_in, target_channel, override, make_thread_named, delete_original)
        except MoveBotWebhookInUse as exc:
            await send_info(txt_channel, None, "MoveBot is in Use",
                            f"{bot_name} is copying messages in this server right now. You must wait for it to finish before asking it to copy again.\n{exc.description()}")
            return
        
        if new_channel:
            dest_channel = f'<#{new_channel.id}>'

        if moved or failed:
            await msg_in.add_reaction("📪")
            await notify_users(aborter, msg_in, override, author_map, dest_channel, delete_original, extra_message, source_channel, failed)
            mod_channel = await send_to_mod_channel(mod_channel, msg_in, moved, failed, dest_channel, delete_original, source_channel)
        await msg_in.add_reaction("🗑")
        if delete_original == 2:
            await delete_messages(aborter, txt_channel, moved + failed + [msg_in])
        elif delete_original == 1:
            await delete_messages(aborter, txt_channel, moved + [msg_in])
        else:
            await delete_messages(aborter, msg_in.channel, [msg_in])

async def abort_movebot(msg_in):
        action = f'<@!{msg_in.author.id}> in <#{msg_in.channel.id}>'
        aborter = MoveBotAborter(msg_in.channel, msg_in.guild.id, action, msg_in.content)
        async with msg_in.channel.typing(), aborter:
            active = [ mb for mb in aborter.movebots_in_guild() if mb is not aborter ]
            active.sort()
            status = 'Aborting all running MoveBot operations on this server:\n' + '\n'.join([ f'{mb.where}\n{mb.operation}' for mb in active ])
            if not active:
                msg_in.channel.send('There are no operations to abort!')
                return
            mod_channel = discord.utils.get(msg_in.guild.channels, name="mod-log")
            if mod_channel:
                await mod_channel.send(content=f'<@!{msg_in.author.id}> is aborting all running MoveBot operations.')
            status_message = await msg_in.channel.send(status)
            for tries in range(30):
                aborter.abort_others()
                await asyncio.sleep(1)
                new_active = [ mb for mb in aborter.movebots_in_guild() if mb is not aborter ]
                new_active.sort()
                if active != new_active:
                    active = new_active
                    if active:
                        status = 'Aborting all running MoveBot operations on this server:\n' + '\n'.join([ f'{mb.where}\n{mb.operation}' for mb in active ])
                        await status_message.edit(content=status)
                    else:
                        await status_message.edit(content=f'All running MoveBot operations on this server have been aborted by request of <@!{msg_in.author.id}>')
                        return
            status = 'Failed to abort some MoveBot operations:\n' + '\n'.join([ f'{mb.where}\n{mb.operation}' for mb in active ])
            await status_message.edit(content = status)


async def fetch_moved_message(msg_in, params, is_reply):
        txt_channel = msg_in.channel
        try:
            #return await txt_channel.fetch_message(msg_in.reference.message_id if is_reply else params[1])
            if is_reply:
                return await txt_channel.fetch_message(msg_in.reference.message_id), None
            try:
                source_channel_id = as_channel_id(params[1])
                source_channel = msg_in.guild.get_channel_or_thread(source_channel_id)
                if not source_channel:
                    return await txt_channel.fetch_message(int(params[1])), None
                elif source_channel and not isinstance(source_channel, discord.Thread):
                    await send_info(txt_channel, None, f"Cannot move <#{source_channel.id}>",
                                    f"{bot_name} can only move threads and messages.\nTry `{LISTEN_TO}help`")
                    return None, None
            except (TypeError, ValueError, AttributeError) as exc:
                await send_info(txt_channel, exc, f"What is that?",
                                f"{bot_name} can only move threads and messages. Don't know what to do with {params[1]}\nTry `{LISTEN_TO}help`")
                return None, None
            if source_channel:
                async for first in source_channel.history():
                    return first, source_channel
            return await txt_channel.fetch_message(params[1]), None
        except Exception as exc:
            await send_info(txt_channel, exc, "Cannot find message",
                              "You can ignore the message ID by executing the **move** command as a reply to the target message.")
            return None,None

async def fetch_other_messages(aborter, is_reply, msg_in, params, moved_msg, source_channel, mod_channel):
        txt_channel = msg_in.channel
        channel_param = 1 if is_reply else 2
        before_messages = []
        after_messages = []
        sleeper = Sleeper(FETCH_SLEEP_TIME)
        if source_channel:
            if not source_channel.permissions_for(msg_in.author).manage_messages:
                send_channel = mod_channel if mod_channel else txt_channel
                await send_channel.send(f"Ignoring command from user <@!{msg_in.author.id}> because they don't have manage_messages permissions on origin channel <#{source_channel.id}>.")
                await msg_in.add_reaction("🚫")
                return ( None, None, None, None )
            count = 0
            async for msg in source_channel.history(before=moved_msg):
                aborter.checkpoint()
                await sleeper.nap()
                count += 1
                if count > MAX_MESSAGES:
                    await send_info(txt_channel, None, f'Thread is too large. Maximum allowed messages is {MAX_MESSAGES}.')
                    break
                before_messages.append(msg)
            dest_channel = params[channel_param]
            extra_message = f'\n\n{params[channel_param + 1]}' if len(params) > channel_param + 1 else ''
        elif params[channel_param].startswith(('+', '-', '~')):
            value = int(params[channel_param][1:])
            if params[channel_param][0] in '+-' and value > MAX_MESSAGES-1:
                await send_info(txt_channel, None, f'Maximum allowed messages is {MAX_MESSAGES}.')

            if params[channel_param][0] == '-':
                async for msg in txt_channel.history(limit=value, before=moved_msg):
                    await sleeper.nap()
                    aborter.checkpoint()
                    before_messages.append(msg)
            elif params[channel_param][0] == '+':
                async for msg in txt_channel.history(limit=value, after=moved_msg):
                    await sleeper.nap()
                    aborter.checkpoint()
                    after_messages.append(msg)
            else:
                try:
                    await txt_channel.fetch_message(value)
                except Exception as exc:
                    await send_info(txt_channel, exc, "Cannot find message",
                                     'An invalid destination message ID was provided.')
                    return ( None, None, None, None )

                found = False
                async for msg in txt_channel.history(limit=MAX_MESSAGES-1, after=moved_msg):
                    aborter.checkpoint()
                    await sleeper.nap()
                    after_messages.append(msg)
                    found = msg.id == value
                    if found:
                        break
                if not found:
                    await send_info(txt_channel, None, 'Cannot find message',
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
        if len(dest_channel) > 1 and dest_channel[0] != '<' and dest_channel[1] in '0123456789':
            dest_channel = '<'+dest_channel+'>'
        before_messages.reverse()
        return ( extra_message, before_messages, after_messages, dest_channel )

async def find_target_channel(msg_in, dest_channel, mod_channel):
        try:
            target_channel = msg_in.guild.get_channel_or_thread(int(dest_channel.strip('<#').strip('>')))
        except Exception as exc:
            await send_info(txt_channel, exc, "Cannot find channel.", "An invalid channel or thread was provided.")
            return None

        if not target_channel.permissions_for(msg_in.author).manage_messages:
            send_channel = mod_channel if mod_channel else msg_in.channel
            await send_mod_log(send_channel, f"Ignoring command from user <@!{msg_in.author.id}> because they don't have manage_messages permissions on destination channel <#{target_channel.id}>.")
            await msg_in.add_reaction("🚫")
            return None

        if target_channel.type == discord.ChannelType.forum and not target_channel.permissions_for(msg_in.author).create_public_threads:
            send_channel = mod_channel if mod_channel else msg_in.channel
            await send_mod_log(send_channel, f"Ignoring command from user <@!{msg_in.author.id}> because they don't have create_public_threads permissions on destination forum <#{target_channel.id}>.")
            await msg_in.add_reaction("🚫")
            return None

        return target_channel

async def copy_messages(aborter, before_messages, moved_msg, after_messages, msg_in, target_channel, override, make_thread_named: str, delete_original):
        webhook_name = f'MoveBot {BOT_ID}'
        guild_id = msg_in.guild.id
        wb = None
        wbhks = await msg_in.guild.webhooks()
        for wbhk in wbhks:
            if wbhk.name == webhook_name:
                wb = wbhk

        parent_channel = target_channel.parent if isinstance(target_channel, Thread) else target_channel
        if wb is None:
            wb = await parent_channel.create_webhook(name=webhook_name, reason='Required webhook for MoveBot to function.')
        else:
            if wb.channel != parent_channel:
                await wb.edit(channel=parent_channel)

        new_thread = None

        author_map = {}
        strip_ping = int(await get_pref(guild_id, "strip_ping", override))
        moved = []
        failed = []
        guild = None
        make_thread = not not make_thread_named
        send_sleeper = Sleeper(SEND_SLEEP_TIME)
        for msg in before_messages + [moved_msg] + after_messages:
            aborter.checkpoint()
            await send_sleeper.nap()
            if guild is None:
                guild = msg.guild

            msg_content = msg.content or msg.system_content or '\u200b'
            if strip_ping == 1 and '@' in msg.content:
                msg_content = msg_content.replace('@', '@\u200b')

            files = []
            for file in msg.attachments:
                files.append(await file.to_file(filename=file.filename, spoiler=file.is_spoiler(), description=file.description if file.description else None))
                # f = io.BytesIO()
                # await file.save(f)
                # files.append(discord.File(f, filename=file.filename, spoiler=file.is_spoiler(), description=file.description if file.description else None))

            kwargs = {
                'content':msg_content,
                'username':msg.author.display_name,
                'avatar_url':msg.author.avatar,
                'embeds':msg.embeds,
                'files':files,
                'wait':True,
            }

            if make_thread:
                if isinstance(target_channel, discord.TextChannel) and not target_channel.type==discord.ChannelType.forum:
                    new_thread = await target_channel.create_thread(name=make_thread_named, reason='MoveBot command', type=discord.ChannelType.public_thread)
                    kwargs['thread'] = new_thread
                else:
                    kwargs['thread_name'] = str(make_thread_named)
            elif new_thread:
                kwargs['thread'] = new_thread
            elif isinstance(target_channel, Thread):
                kwargs['thread'] = target_channel

            fail_counter = 0
            for retry in range(2):
                if retry == 1:
                    failed.append(msg)
                    if delete_original > 1:
                        kwargs['content'] = f'{bot_name} could not copy this message, so it only copied the text.\n'
                    else:
                        kwargs['content'] = f'{bot_name} could not copy message {msg.jump_url} to this channel.\n'
                    kwargs['embeds'] = [ discord.Embed(title=f"Message Contents", description=msg_content) ]
                    del kwargs['files']
                    fail_counter += 1
                try:
                    sm = await(wb.send(**kwargs))
                    if not retry:
                        moved.append(msg)
                    break
                except discord.DiscordException as he:
                    pass
                if MAX_FAILED_COPIES>0 and len(failed)>=MAX_FAILED_COPIES:
                    send_info(msg_in.channel, None, "Too many failed copies",
                              f'Gave up copying messages after {MAX_FAILED} failed copy attempts.')
                    break

            if make_thread and sm.channel:
                new_thread = sm.channel
                make_thread = False

            if msg.author.id not in author_map:
                author_map[msg.author.id] = msg.author
        return ( moved, failed, author_map, new_thread )

async def send_to_mod_channel(mod_channel, msg_in, moved, failed, dest_channel, delete_original, source_channel):
        if not mod_channel:
            mod_channel = discord.utils.get(msg_in.guild.channels, name="mod-log")
        if mod_channel:
            txt_channel = source_channel if source_channel else msg_in.channel
            description = "CC_OPERATION MESSAGE_COUNT messages from SOURCE_CHANNEL to DESTINATION_CHANNEL, ordered by MOVER_USER."
            description = description.replace("MESSAGE_COUNT", str(len(moved) + len(failed))) \
                                     .replace("SOURCE_CHANNEL", f"<#{txt_channel.id}>") \
                                     .replace("DESTINATION_CHANNEL", dest_channel) \
                                     .replace("MOVER_USER", f"`{msg_in.author.name}`") \
                                     .replace("LC_OPERATION", 'moved' if delete_original else 'copied') \
                                     .replace("CC_OPERATION", 'Moved' if delete_original else 'Copied')
            await send_mod_log(mod_channel, description)
        return mod_channel

async def notify_users(aborter, msg_in, override, author_map, dest_channel, delete_original, extra_message, source_channel, failed):
        guild_id = msg_in.guild.id
        notify_dm = int(await get_pref(guild_id, "notify_dm", override))
        authors = [author_map[a] for a in author_map]
        author_ids = [f"<@!{a.id}>" for a in authors]
        send_objs = []
        if notify_dm == 1:
            send_objs = authors
        elif notify_dm != 2:
            send_objs = [source_channel if source_channel else msg_in.channel]
        if notify_dm != 2:
            for send_obj in send_objs:
                aborter.checkpoint()
                if notify_dm == 1:
                    message_users = f"<@!{send_obj.id}>"
                elif len(author_ids) == 1:
                    message_users = author_ids[0]
                else:
                    message_users = f'{", ".join(author_ids[:-1])}{"," if len(author_ids) > 2 else ""} and {author_ids[-1]}'
                description = await get_pref(guild_id, "move_message", override)
                if not description:
                    description = available_prefs['move_message']
                description = description.replace("MESSAGE_USER", message_users) \
                    .replace("DESTINATION_CHANNEL", dest_channel) \
                    .replace("MOVER_USER", f"<@!{msg_in.author.id}>") \
                    .replace("LC_OPERATION", 'moved' if delete_original else 'copied') \
                    .replace("CC_OPERATION", 'Moved' if delete_original else 'Copied')
                description = f'{description}{extra_message}'
                if failed:
                    if delete_original>1:
                        description += f"\n\nMoveBot couldn't copy {len(failed)} message{'s' if len(failed)>1 else ''}, so it only copied the text."
                    else:
                        description += f"\n\nThese messages were linked instead of copied because MoveBot couldn't move them: "
                        description += ', '.join([ m.jump_url for m in failed ])
                embed = int(await get_pref(guild_id, "embed_message", override))
                try:
                    if embed == 1:
                        e = discord.Embed(title="Message Moved")
                        e.description = description
                        await send_obj.send(embed=e)
                    elif description:
                        await send_obj.send(description)
                except (discord.NotFound, commands.errors.MessageNotFound) as exc:
                    to = f'`{send_boj.id}`' if notify_dm == 1 else f'<#{send_obj.id}>'
                    await send_info(msg_in.channel, exc, "Cannot send message",
                                    f'Unable to send notification message to {to}')

async def delete_messages(aborter, log_channel, messages):
        # Split messages into blocks of MAX_DELETE or less for bulk deletion.
        bulk_delete = {}

        # Messages too old cannot be bulk deleted. We'll delete them one by one instead.
        one_by_one = []

        # Detect and discard duplicates:
        seen = set()

        for msg in messages:
            if not msg or not msg.channel or msg.id in seen:
                continue
            seen.add(msg.id)
            age = (datetime.datetime.now(datetime.timezone.utc) - msg.created_at).total_seconds()
            if age > BULK_DELETE_MAX_AGE:
                one_by_one.append(msg)
            else:
                channel_bulk_delete = bulk_delete.setdefault(msg.channel, [[]])
                if len(channel_bulk_delete[-1]) >= MAX_DELETE:
                    channel_bulk_delete.append([])
                channel_bulk_delete[-1].append(msg)

        # Delete messages if desired.
        try:
            delete_sleeper = Sleeper(DELETE_SLEEP_TIME)
            for channel,channel_bulk_delete in bulk_delete.items():
                for batch in channel_bulk_delete:
                    if aborter:
                        aborter.checkpoint()
                    await delete_sleeper.nap()
                    await channel.delete_messages(batch)
            for msg in one_by_one:
                if aborter:
                    aborter.checkpoint()
                await delete_sleeper.nap()
                await msg.delete()
            return True
        except (discord.NotFound, commands.errors.MessageNotFound) as exc:
            await send_info(log_channel, exc, "Deletion failed: unknown message",
                             "Some messages may not have been deleted. "
                             "The bot attempted to delete a message, but could not find it. "
                             "Did someone already delete it? "
                             + f"Was it a part of a `{LISTEN_TO}+/-**x** #\channel` command?")
        except Exception as exc:
            await send_info(log_channel, exc, "Deletion failed.",
                             "Some messages may not have been deleted. "
                             + "Please check the permissions (just apply **Admin** to the bot or its role for EasyMode)")
        return False
#end
bot.run(TOKEN)
