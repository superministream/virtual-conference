import sys
import pprint
import re
import os
import discord

import core.schedule as schedule

USAGE = """
./make_poster_discord_channels.py <schedule_db.xlsx> <discord guild id>
"""

if len(sys.argv) != 3:
    print(USAGE)
    sys.exit(1)

discord_guild_id = sys.argv[2]
database = schedule.Database(sys.argv[1], discord=True)
poster_info = database.workbook.get_table("posters")

client = discord.Client()
@client.event
async def on_ready():
    print("Making Discord channels for posters")
    guild = [g for g in client.guilds if str(g.id) == discord_guild_id][0]

    # All poster channels are under the "posters" category, which I created manually
    poster_category = [ec for ec in guild.categories if ec.name == "posters"][0]

    # Make sure each poster has a Discord channel
    for r in poster_info.items():
        if not r["Event ID"].value:
            break
        if r["Discord Channel ID"].value:
            continue

        channel_name = schedule.make_disord_channel_name(r["Title"].value)
        channel = await poster_category.create_text_channel(channel_name)

        r["Discord Channel ID"].value = str(channel.id)
        r["Discord Channel URL"].value = f"https://discord.com/channels/{guild.id}/{channel.id}"
        database.save("poster_channels_made.xlsx")

    print("Saving database")
    database.save("poster_channels_made.xlsx")
    print("Setup complete, hit ctrl-c to end bot and exit")

client.run(database.auth.discord["bot_token"])
