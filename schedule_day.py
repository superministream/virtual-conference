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

if len(sys.argv) < 6:
    print("Usage: {} <data sheet.xlsx> <day> <discord guild id> <thumbnail file> <font root>".format(sys.argv[0]))
    sys.exit(1)

discord_guild_id = sys.argv[3]
thumbnail_params = {
    "background": sys.argv[4],
    # NOTE: You'll want to change these font file names with the ones you're using
    # in your streaming software.
    "bold_font": os.path.join(sys.argv[5], "MPLUSRounded1c-Black.ttf"),
    "regular_font": os.path.join(sys.argv[5], "MPLUSRounded1c-Regular.ttf")
}

database = schedule.Database(sys.argv[1], youtube=True, use_pickled_credentials=True)
# Fill in the computer stream key IDs
database.populate_stream_key_ids()

day = database.get_day(sys.argv[2])
sessions = day.get_sessions(False)

computers = []
for c in database.computers.items():
    if not c["Youtube Stream Key ID"].value:
        print("Failed to get stream key ID for computer {}, aborting!".format(c["ID"].value))
        sys.exit(1)
    # All computers are initially marked as available starting at midnight
    avail_at = datetime(schedule.CONFERENCE_YEAR, day.month, day.day, hour=0, minute=1, tzinfo=schedule.conf_tz)
    # We also include the ID as a tiebreaker for when all the computers have the same time,
    # since the dicts are not comparable
    heappush(computers, (avail_at, c["ID"].value, c))

for k, v in sessions.items():
    avail_at, pc_id, next_computer = heappop(computers)
    session_time = v.session_time()
    # We need some setup time ahead of the session's start time to do A/V check with the presenters
    need_at = session_time[0] - v.setup_time()
    if avail_at > need_at:
        print("The next available computer isn't available until {},".format(schedule.format_time(avail_at)) + \
              " which is after the next session {} - {} that needs a computer for setup starting at: {}!"
              .format(v.event, v.name, schedule.format_time(need_at)))
        sys.exit(1)

    print("Session streams on computer {}".format(next_computer["ID"].value))
    v.create_virtual_session(next_computer["ID"].value, thumbnail_params)
    print(v)
    database.save(sys.argv[2] + "_scheduled.xlsx")
    print("------")
    # The computer is available again 10 minutes after this session ends for buffer
    avail_at = session_time[1] + timedelta(minutes=10)
    heappush(computers, (avail_at, pc_id, next_computer))

if "--no-discord" in sys.argv:
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
    events = set()
    for k, v in sessions.items():
        events.add(v.chat_category_name())

    event_categories = {}
    for e in events:
        event_category = [ec for ec in guild.categories if ec.name == e]
        if len(event_category) == 0:
            event_categories[e] = await guild.create_category(e)
        else:
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

