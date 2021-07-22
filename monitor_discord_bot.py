import sys
import re
import json
import discord
import os
import pickle

import core.auth as conf_auth
import core.bot_base as base

# This bot monitors all channels in the guild for Zoom links and
# warns people to make sure they set a password and waiting room
# It also monitors the support channel for users requesting their
# messages to not be sync'd to Youtube. This bot can be started
# at the beginning of the conference and left running the entire time.


if(not "DATA_FOLDER" in os.environ):
    print("You must set $DATA_FOLDER to a folder which contains the working data of this tool.")
    sys.exit(1)

# discordIDs.dat is supposed to be a dict, containing all relevant guild IDs from Discord.
# That way, you don't have to pass all IDs via commandline arguments.
# To create the discordIDs.dat, you can use the create_discordIDs.py

f = open(os.environ["DATA_FOLDER"] + "/discordIDs.dat", "rb")
discordIDs = pickle.load(f)
f.close()

discord_server_id = discordIDs["Server"]
sync_channel_id = discordIDs["SyncChannel"]

auth = conf_auth.Authentication()
client = discord.Client()

file_name = os.environ["DATA_FOLDER"] + "/chat_sync_filter_users.json"

@client.event
async def on_ready():
    guild = [g for g in client.guilds if g.id == discord_server_id][0]
    print("Monitoring server {} for zoom links".format(guild))

@client.event
async def on_message(msg):
    if msg.author == client.user:
        return

    if msg.guild.id != discord_server_id:
        return
    if msg.channel.id == sync_channel_id and msg.content == "$sync":
        print("sync request by {}".format(msg.author.name))
        users = []
        with open(file_name, "r") as f:
            users = json.load(f)
        if(msg.author.name + msg.author.discriminator in users):
            users.remove(msg.author.name + msg.author.discriminator)
            with open(file_name, "w") as f:
                json.dump(users, f)

        await msg.author.send(content="Your messages will be sync'd to Youtube again.")

    if msg.channel.id == sync_channel_id and msg.content == "$nosync":
        print("no sync request by {}".format(msg.author.name))
        users = []
        with open(file_name, "r") as f:
            users = json.load(f)
        if(msg.author.name + msg.author.discriminator in users):
            await msg.author.send(content="You were already on the nosync list. If you want to get your messages synced again, please message a $sync in the #youtube-sync-commands channel.")
            return

        users.append(msg.author.name + msg.author.discriminator)
        with open(file_name, "w") as f:
            json.dump(users, f)

        await msg.author.send(content="Your messages will not be sync'd to Youtube any longer.")

    if msg.content and base.match_zoom_link.search(msg.content):
        warning = await msg.channel.send("Hi {} that looks like a Zoom link!".format(msg.author.mention) + \
                " Please make sure you've set a meeting password and enabled the waiting room.") 
        await warning.add_reaction("⚠")

client.run(auth.discord["bot_token"])

