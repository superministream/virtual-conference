import sys
import re
import json
import discord

import core.auth as conf_auth
import core.bot_base as base

# This bot monitors all channels in the guild for Zoom links and
# warns people to make sure they set a password and waiting room
# It also monitors the support channel for users requesting their
# messages to not be sync'd to Youtube. This bot can be started
# at the beginning of the conference and left running the entire time.
if len(sys.argv) != 2:
    print("Usage: {} <discord guild id> <support channel id>".format(sys.argv[0]))
    sys.exit(1)

discord_guild_id = int(sys.argv[1])
support_channel_id = int(sys.argv[2])

auth = conf_auth.Authentication()
client = discord.Client()

@client.event
async def on_ready():
    guild = [g for g in client.guilds if g.id == discord_guild_id][0]
    print("Monitoring guild {} for zoom links".format(guild))

@client.event
async def on_message(msg):
    if msg.author == client.user:
        return

    if msg.guild.id != discord_guild_id:
        return

    if msg.channel.id == support_channel_id and msg.content == "$nosync":
        print("no sync request by {}".format(msg.author.name))
        file_name = "chat_sync_filter_users.json"
        users = []
        with open(file_name, "r") as f:
            users = json.load(f)

        users.append(msg.author.name + msg.author.discriminator)
        with open(file_name, "w") as f:
            json.dump(users, f)

        await msg.author.send(content="Your messages will not be sync'd to Youtube")

    if msg.content and base.match_zoom_link.search(msg.content):
        warning = await msg.channel.send("Hi {} that looks like a Zoom link!".format(msg.author.mention) + \
                " Please make sure you've set a meeting password and enabled the waiting room.") 
        await warning.add_reaction("⚠")

client.run(auth.discord["bot_token"])

