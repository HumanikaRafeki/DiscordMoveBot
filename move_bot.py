import os
import io
import json
import discord
import requests
import sqlite3
from contextlib import closing
from discord import Thread
from dotenv import load_dotenv
import logging

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

available_prefs = {
    "notify_dm": "0",
    "embed_message": "0",
    "move_message": "MESSAGE_USER, your message has been moved to DESTINATION_CHANNEL by MOVER_USER",
    "strip_ping": "0"
}
pref_help = {
    "notify_dm": """
**name:** `notify_dm`
**value:**
 `0`  Sends move message in channel
 `1`  Sends move message as a DM
 `2`  Don't send any message

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
`!mv pref send_message MESSAGE_USER, your message belongs in DESTINATION_CHANNEL and was moved by MOVER_USER`

**name:** `strip_ping`
**value:**
`0` Do not strip pings
`1` Strip 'everyone' and 'here' pings

**example:**
`!mv pref strip_ping 1`
    """,
}
prefs = {}
with sqlite3.connect(DB_PATH) as connection:
    connection.row_factory = sqlite3.Row
    with closing(connection.cursor()) as cursor:
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS prefs (
            key INTEGER PRIMARY KEY,
            guild_id INTEGER,
            pref TEXT,
            value TEXT)"""
        )
        cursor.execute(f"SELECT * FROM prefs")
        rows = cursor.fetchall()
        for row in rows:
            g_id = int(row["guild_id"])
            if g_id not in prefs:
                prefs[g_id] = {}
            prefs[g_id][str(row["pref"])] = str(row["value"])

def get_pref(guild_id, pref):
    return prefs[guild_id][pref] if guild_id in prefs and pref in prefs[guild_id] else available_prefs[pref]

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
client = discord.Client(intents=intents)

@client.event
async def on_connect():
    print(f'{client.user} has connected to Discord!')
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f'for spoilers | {LISTEN_TO} help'))

    global admin
    admin = await client.fetch_user(int(ADMIN_ID))

@client.event
async def on_guild_join(guild):
    url=f'https://discordbotlist.com/api/v1/bots/{STATS_ID}/stats'
    headers = {
        "Authorization": STATS_TOKEN,
        "Content-Type": 'application/json'
    }
    payload = json.dumps({
        "guilds": len(client.guilds)
    })
    requests.request("POST", url, headers=headers, data=payload)

    notify_me = f'MoveBot was added to {guild.name} ({guild.member_count} members)! Currently in {len(client.guilds)} servers.'
    await admin.send(notify_me)

@client.event
async def on_guild_remove(guild):
    url=f'https://discordbotlist.com/api/v1/bots/{STATS_ID}/stats'
    headers = {
        "Authorization": STATS_TOKEN,
        "Content-Type": 'application/json'
    }
    payload = json.dumps({
        "guilds": len(client.guilds)
    })
    requests.request("POST", url, headers=headers, data=payload)

    notify_me = f'MoveBot was removed from {guild.name} ({guild.member_count} members)! Currently in {len(client.guilds)} servers.'
    await admin.send(notify_me)

@client.event
async def on_message(msg_in):
    if msg_in.author == client.user or msg_in.author.bot \
            or not msg_in.content.startswith(LISTEN_TO) \
            or not msg_in.author.guild_permissions.manage_messages:
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

            **Method 2: Replying to the target message**
            `!mv [optional multi-move] [#targetChannelOrThread] [optional message]`

            **examples:**
            `!mv #general`
            `!mv #general This message belongs in general.`
            `!mv +2 #general This message and the 2 after it belongs in general.`
            `!mv -3 #general This message and the 3 before it belongs in general.`
            {pref_help_description}
            **Head over to https://discord.gg/t5N754rmC6 for any questions or suggestions!**"
        """
        await msg_in.author.send(embed=e)

    # !mv reset
    elif params[1] == "reset":
        with sqlite3.connect("settings.db") as connection:
            connection.row_factory = sqlite3.Row
            with closing(connection.cursor()) as cursor:
                cursor.execute("DELETE FROM prefs WHERE guild_id = ?", (guild_id,))
        if guild_id in prefs:
            prefs.pop(guild_id)
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
            response_msg = f"`{params[2]}`: `{get_pref(guild_id, params[2])}`"
        elif params[3] == "?":
            response_msg = pref_help[params[2]]
        else:
            title = "Preference Updated"
            with sqlite3.connect(DB_PATH) as connection:
                connection.row_factory = sqlite3.Row
                with closing(connection.cursor()) as cursor:
                    cursor.execute("INSERT OR IGNORE INTO prefs(guild_id, pref) VALUES(?, ?)", (guild_id, params[2]))
                    cursor.execute(f"UPDATE prefs SET value = ? WHERE guild_id = ? AND pref = ?", (params[3], guild_id, params[2]))
            if guild_id not in prefs:
                prefs[guild_id] = {}
            prefs[guild_id][params[2]] = params[3]
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
        if params[channel_param].startswith(('+', '-')):
            value = int(params[channel_param][1:])
            if params[channel_param][0] == '-':
                before_messages = [m async for m in txt_channel.history(limit=value, before=moved_msg)]
                before_messages.reverse()
            else:
                after_messages = [m async for m in txt_channel.history(limit=value, after=moved_msg)]
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
        author_map = {}
        strip_ping = get_pref(guild_id, "strip_ping")
        for msg in before_messages + [moved_msg] + after_messages:
            msg_content = msg.content.replace('@', '@\u200b') if strip_ping == "1" and '@' in msg.content else msg.content
            files = []
            for file in msg.attachments:
                f = io.BytesIO()
                await file.save(f)
                files.append(discord.File(f, filename=file.filename))

            if isinstance(target_channel, Thread):
                await wb.send(content=msg_content, username=msg.author.display_name, avatar_url=msg.author.avatar, embeds=msg.embeds, files=files, thread=target_channel)
            else:
                await wb.send(content=msg_content, username=msg.author.display_name, avatar_url=msg.author.avatar, embeds=msg.embeds, files=files)
            if msg.author.id not in author_map:
                author_map[msg.author.id] = msg.author

        notify_dm = get_pref(guild_id, "notify_dm")
        authors = [author_map[a] for a in author_map]
        author_ids = [f"<@!{a.id}>" for a in authors]
        send_objs = []
        if notify_dm == "1":
            send_objs = authors
        elif notify_dm != "2":
            send_objs = [txt_channel]
        if send_objs:
            for send_obj in send_objs:
                if notify_dm == "1":
                    message_users = f"<@!{send_obj.id}>"
                elif len(author_ids) == 1:
                    message_users = author_ids[0]
                else:
                    message_users = f'{", ".join(author_ids[:-1])}{"," if len(author_ids) > 2 else ""} and {author_ids[-1]}'
                description = get_pref(guild_id, "move_message") \
                    .replace("MESSAGE_USER", message_users) \
                    .replace("DESTINATION_CHANNEL", dest_channel) \
                    .replace("MOVER_USER", f"<@!{msg_in.author.id}>")
                description = f'{description}{extra_message}'
                embed = get_pref(guild_id, "embed_message") == "1"
                if embed:
                    e = discord.Embed(title="Message Moved")
                    e.description = description
                    await send_obj.send(embed=e)
                else:
                    await send_obj.send(description)
        for msg in before_messages + [moved_msg, msg_in] + after_messages:
            await msg.delete()

#end
client.run(TOKEN)
