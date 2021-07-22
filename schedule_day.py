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

if(not "DATA_FOLDER" in os.environ):
    print("You must set $DATA_FOLDER to a folder which contains the working data of this tool.")
    sys.exit(1)

if len(sys.argv) < 5:
    print("Usage: {} <data sheet.xlsx> <day> <thumbnail file> <font root>".format(sys.argv[0]))
    sys.exit(1)

def getNextAvailableMachine(computers, time):
    for computer_id in computers.keys():
        avail_at, pc_id = computers[computer_id]
        if(avail_at <= time):
            return pc_id
    return None

f = open(os.environ["DATA_FOLDER"] + "/discordIDs.dat", "rb")
discordIDs = pickle.load(f)
f.close()

discord_guild_id = discordIDs["Server"]
thumbnail_params = {
    "background": sys.argv[3],
    # NOTE: You'll want to change these font file names with the ones you're using
    # in your streaming software.
    "bold_font": os.path.join(sys.argv[4], "MPLUSRounded1c-Black.ttf"),
    "regular_font": os.path.join(sys.argv[4], "MPLUSRounded1c-Regular.ttf")
}

database = schedule.Database(sys.argv[1], youtube=True, use_pickled_credentials=True)
# Fill in the computer stream key IDs
database.populate_stream_key_ids()

day = database.get_day(sys.argv[2])
sessions = day.get_sessions(False)

event_dict = {}

computer_dict = {}

for c in database.computers.items():
    if not c["Youtube Stream Key ID"].value:
        print("Failed to get stream key ID for computer {}, aborting!".format(c["ID"].value))
        sys.exit(1)
    # All computers are initially marked as available starting at midnight
    avail_at = datetime(schedule.CONFERENCE_YEAR, day.month, day.day, hour=0, minute=1, tzinfo=schedule.conf_tz)
    # We also include the ID as a tiebreaker for when all the computers have the same time,
    # since the dicts are not comparable
    computer_dict[c["ID"].value] = (avail_at, c["ID"].value)

for k, v in sessions.items():
    session_time = v.session_time()
    if(v.event not in event_dict.keys()):
        event_dict[v.event] = getNextAvailableMachine(computer_dict, session_time[0] - v.setup_time())
    current_computer = event_dict[v.event]
    avail_at, pc_id = computer_dict[current_computer]
    # We need some setup time ahead of the session's start time to do A/V check with the presenters
    need_at = session_time[0] - v.setup_time()
    if(avail_at > need_at):
        print("Parallel session of same type?")
        current_computer = getNextAvailableMachine(computer_dict, session_time[0] - v.setup_time())
        avail_at, pc_id = computer_dict[current_computer]
    if avail_at > need_at:
        print("The next available computer isn't available until {},".format(schedule.format_time(avail_at)) + \
              " which is after the next session {} - {} that needs a computer for setup starting at: {}!"
              .format(v.event, v.name, schedule.format_time(need_at)))
        sys.exit(1)

    print("Session streams on computer {}".format(pc_id))
    v.create_virtual_session(pc_id, thumbnail_params)
    print(v)
    database.save("../../Schedule/" + sys.argv[2] + "_scheduled.xlsx")
    print("------")
    # The computer is available again 10 minutes after this session ends for buffer
    avail_at = session_time[1] + timedelta(minutes=10)
    computer_dict[current_computer] = (avail_at, pc_id)

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

