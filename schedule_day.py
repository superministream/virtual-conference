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

if setup_discord and not "DATA_FOLDER" in os.environ:
    print("You must set $DATA_FOLDER to a folder which contains the working data of this tool.")
    sys.exit(1)

if len(sys.argv) < 5:
    print("Usage: {} <data sheet.xlsx> <day> <thumbnail file> <font root>".format(sys.argv[0]))
    sys.exit(1)

discord_guild_id = None
if setup_discord:
    f = open(os.environ["DATA_FOLDER"] + "/discordIDs.dat", "rb")
    discordIDs = pickle.load(f)
    f.close()
    discord_guild_id = discordIDs["Server"]

# Off for testing
thumbnail_params = None
#thumbnail_params = {
#    "background": sys.argv[3],
    # NOTE: You'll want to change these font file names with the ones you're using
    # in your streaming software.
    #"bold_font": os.path.join(sys.argv[4], "MPLUSRounded1c-Black.ttf"),
    #"regular_font": os.path.join(sys.argv[4], "MPLUSRounded1c-Regular.ttf")
#}

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
            if track != v.track():
                continue
            session_time = v.session_time()
            if track_start == None or session_time[0] < track_start:
                track_start = session_time[0]
            if track_end == None or session_time[1] > track_end:
                track_end = session_time[1]

        track_start = track_start - timedelta(minutes=30)
        track_end = track_end + timedelta(minutes=30)

        host = c["Zoom Host ID"].value
        alternative_hosts = [comp["Zoom Host ID"].value for comp in computers if comp["ID"].value != track]

        zoom_info = schedule.schedule_zoom_meeting(database.auth, title, password, track_start, track_end,
                "Conference", host, alternative_hosts=alternative_hosts)
        c[f"Zoom URL {day_name}"].value = zoom_info["join_url"]
        c[f"Zoom Meeting ID {day_name}"].value = str(zoom_info["id"])
        c[f"Zoom password {day_name}"].value = password

database.save(sys.argv[2] + "_scheduled.xlsx")

for k, v in sessions.items():
    session_time = v.session_time()
    session_track = v.get_track()

    print(f"Session streams on computer/track {session_track}")
    v.create_virtual_session(thumbnail_params)
    print(v)
    database.save(sys.argv[2] + "_scheduled.xlsx")
    print("------")

if not setup_discord:
    print("Not creating Discord channels")
    sys.exit(0)

# Really annoying but have to run bot to create channels since there's no way to just make
# basic synchronous API calls through the discord python wrapper
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

    # Make a category for each event and a general channel for the event
    # Store Session Category in Events set
    events = set()
    for k, v in sessions.items():
        events.add(v.chat_category_name())

    event_categories = {}
    # Store Event Category in dict (create it, if it doesn't exist yet)
    for e in events:
        event_category = [ec for ec in guild.categories if ec.name == e]
        if len(event_category) == 0:
            # Create new Discord Category if it doesn't exist yet
            event_categories[e] = await guild.create_category(e)
        else:
            # Store Discord Category, if it already exists
            event_categories[e] = event_category[0]

    for k, v in sessions.items():
        # Meetups are just Zoom meetings
        if v.timeslot_entry(0, "Time Slot Type").value == "Zoom Only":
            continue

        event_category = event_categories[v.chat_category_name()]
        channel_name = v.chat_channel_name()
        c = [c for c in event_category.text_channels if c.name == channel_name]
        print_session_info = False
        if len(c) == 0:
            c = await event_category.create_text_channel(channel_name)
            # Print and pin the schedule to the channel
            session_info = await c.send(embed=discord.Embed.from_dict(v.discord_embed_dict()))
            await session_info.pin()

            new_channels.append(channel_name)
        else:
            c = c[0]

        for t in range(0, len(v.timeslots)):
            v.timeslot_entry(t, "Discord Channel").value = c.name
            v.timeslot_entry(t, "Discord Link").value = "https://discord.com/channels/{}/{}".format(guild.id, c.id)
            v.timeslot_entry(t, "Discord Invite Link").value = str(discord_invite)

        # Update the Youtube description with the Discord link
        v.update_youtube_broadcast_description()

    print("Saving database")
    database.save(sys.argv[2] + "_scheduled.xlsx")
    print("Setup complete, hit ctrl-c to end bot and exit")

client.run(database.auth.discord["bot_token"])

