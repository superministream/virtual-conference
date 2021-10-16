import sys
import os
import json
import discord
from datetime import datetime, timedelta
from heapq import heappush, heappop

import core.schedule as schedule

# This script will create the YouTube broadcasts, Zoom Meetings and Discord channels
# for each session in your conference and assign them to specific computers for streaming
# during the event.
setup_discord = not "--no-discord" in sys.argv

if len(sys.argv) < 6:
    print("Usage: {} <data sheet.xlsx> <day> <thumbnail file> <font root> <assets root>".format(sys.argv[0]))
    sys.exit(1)

discord_guild_id = None
if setup_discord and len(sys.argv) < 7:
    print("Usage: {} <data sheet.xlsx> <day> <thumbnail file> <font root> <assets root> <discord guild ID>".format(sys.argv[0]))
    sys.exit(1)

if setup_discord:
    discord_guild_id = sys.argv[6]

# Off for testing
thumbnail_params = {
    "background": sys.argv[3],
    # NOTE: You'll want to change these font file names with the ones you're using
    # in your streaming software.
    "fonts": {
        "bold": os.path.join(sys.argv[4], "bold-font.ttf"),
        "italic": os.path.join(sys.argv[4], "italic-font.ttf"),
        "regular": os.path.join(sys.argv[4], "regular-font.ttf"),
    },
    "asset_root_dir": sys.argv[5]
}

database = schedule.Database(sys.argv[1], youtube=True, use_pickled_credentials=True)
# Fill in the computer stream key IDs
database.populate_stream_key_ids()
database.populate_zoom_host_ids()

day_name = sys.argv[2]
day = database.get_day(day_name)
sessions = day.get_sessions(False)

computers = database.computers.items()

# Check that the Zoom meetings have been created for each computer for this day
# and if not create them spanning the time we need for the conference +/- 30min
for c in computers:
    if not c[f"Zoom URL {day_name}"].value:
        track = c["ID"].value
        password = schedule.generate_password()
        title = f"{schedule.CONFERENCE_NAME}: {day_name}  track {track}"

        # Find the start time of the first session and end time of the last one in the track
        track_start = None
        track_end = None
        for k, v in sessions.items():
            if track != v.get_track():
                continue
            session_time = v.session_time()
            if track_start == None or session_time[0] < track_start:
                track_start = session_time[0]
            if track_end == None or session_time[1] > track_end:
                track_end = session_time[1]

        if not track_start:
            print(f"Skipping unused track {track} on {day_name}")
            continue

        track_start = track_start - timedelta(minutes=30)
        track_end = track_end + timedelta(minutes=30)

        host = c["Zoom Host ID"].value
        alternative_hosts = [comp["Zoom Host ID"].value for comp in computers if comp["ID"].value != track]

        zoom_info = schedule.schedule_zoom_meeting(database.auth, title, password, track_start, track_end,
                "Conference", host, alternative_hosts=alternative_hosts)
        c[f"Zoom URL {day_name}"].value = zoom_info["join_url"]
        c[f"Zoom Meeting ID {day_name}"].value = str(zoom_info["id"])
        c[f"Zoom Password {day_name}"].value = password

database.save(day_name + "_scheduled.xlsx")

for k, v in sessions.items():
    session_time = v.session_time()
    session_track = v.get_track()

    print(f"Session streams on computer/track {session_track}")
    v.create_virtual_session(thumbnail_params)
    print(v)
    database.save(day_name + "_scheduled.xlsx")
    print("------")

if not setup_discord:
    print("Not creating Discord channels")
    sys.exit(0)

# Really annoying but have to run bot to create channels since there's no way to just make
# basic synchronous API calls through the discord python wrapper
# Now we only have one channel per room on Discord
new_channels = []
client = discord.Client()
@client.event
async def on_ready():
    print("Making Discord channels")
    guild = [g for g in client.guilds if str(g.id) == discord_guild_id][0]
    unlimited_invite = [i for i in await guild.invites() if i.max_age == 0 and i.max_uses == 0]
    discord_invite = None
    if len(unlimited_invite) == 0:
        print("No unlimited/infinite invite for the Guild, creating one now")
        discord_invite = await guild.text_channels[0].create_invite(max_age=0, max_uses=0)
    else:
        discord_invite = unlimited_invite[0]

    # All track channels are under the "tracks" category, which I created manually
    track_category = [ec for ec in guild.categories if ec.name == "tracks"][0]

    # Make sure each room has a discord channel
    for comp in computers:
        if comp["Discord Channel ID"].value:
            continue

        channel_name = schedule.make_disord_channel_name(comp["Name"].value)
        channel = await track_category.create_text_channel(channel_name)

        comp["Discord Channel ID"].value = str(channel.id)
        comp["Discord Link"].value = f"https://discord.com/channels/{guild.id}/{channel.id}"
        comp["Discord Invite Link"].value = str(discord_invite)

    # Populate the discord info in the session sheet
    for k, v in sessions.items():
        v.populate_discord_info()

    print("Saving database")
    database.save(day_name + "_scheduled.xlsx")
    print("Setup complete, hit ctrl-c to end bot and exit")

client.run(database.auth.discord["bot_token"])

