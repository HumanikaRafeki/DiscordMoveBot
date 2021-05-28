import os
import io
import json
import discord
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
STATS_TOKEN = os.getenv('STATS_TOKEN')
LISTEN_TO = os.getenv('LISTEN_TO')
ADMIN_ID = os.getenv('BLACKRAINBOW_UID')
BOT_ID = os.getenv('MOVEBOT_ID')

intents = discord.Intents.all()
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f'for spoilers | {LISTEN_TO} help'))

    global admin
    admin = await client.fetch_user(user_id=ADMIN_ID)

@client.event
async def on_guild_join(guild):
    url=f'https://discordbotlist.com/api/v1/bots/{BOT_ID}/stats'
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
    url=f'https://discordbotlist.com/api/v1/bots/{BOT_ID}/stats'
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
    if msg_in.author == client.user:
        return

    if msg_in.author.bot:
        return

    if msg_in.content.startswith(LISTEN_TO):
        txt_channel = msg_in.channel
        params = msg_in.content.split()

        # !mv help
        if params[1] == 'help':
            e = discord.Embed(title="MoveBot Help")
            e.description = \
                "This bot can move messages in two different ways.\n" + \
                "*Moving messages requires to have the 'Manage messages' permission.*\n\n" + \
                "**Method 1: Using the target message's ID**\n" + \
                "!mv [messageID] [#targetChannel]\n\n" + \
                "**Method 2: Replying to the target message**\n" + \
                "!mv [#targetChannel]\n\n" + \
                "*Feel free to contact **N3X4S#6792** for any question or suggestion!*"
            await msg_in.author.send(embed=e)

        # !mv [msgID] [#channel]
        else:
            if msg_in.author.guild_permissions.manage_messages:
                error_msg = ''
                channel_param = 2
                try:
                    if msg_in.reference is not None:
                        moved_msg = await txt_channel.fetch_message(msg_in.reference.message_id)
                        channel_param = 1
                    else:
                        moved_msg = await txt_channel.fetch_message(params[2])
                except:
                    error_msg = error_msg + 'An invalid message ID was provided. You can ignore the message ID by executing the **move** command as a reply to the target message'

                try:
                    target_channel = client.get_channel(int(params[channel_param].strip('<#').strip('>')))
                except:
                    error_msg = error_msg + "An invalid channel was provided. "

                if len(error_msg) != 0:
                    await txt_channel.send(error_msg)
                else:
                    wb = await target_channel.create_webhook(name=moved_msg.author.display_name)

                    files = []
                    for file in moved_msg.attachments:
                        f = io.BytesIO()
                        await file.save(f)
                        files.append(discord.File(f, filename=file.filename))

                    await wb.send(content=moved_msg.content, avatar_url=moved_msg.author.avatar_url, embeds=moved_msg.embeds, files=files)
                    await wb.delete()

                    notice_msg = f'<@!{moved_msg.author.id}>, your message has been moved to {params[channel_param]} by <@!{msg_in.author.id}>'

                    await txt_channel.send(notice_msg)
                    await msg_in.delete()
                    await moved_msg.delete()

#end
client.run(TOKEN)
