import sys
import json
import discord
from datetime import timezone, datetime, timedelta

import core.schedule as schedule

if "-h" in sys.argv or len(sys.argv) != 5:
    print("""Usage: {} <data sheet.xlsx> <day> <time end> <time start>

    Advance the streams to the next broadcasts to be made live, and make those broadcasts live.
    Will take offline the broadcasts that ended within the [<time end>, <time start>] interval
    and make those starting within the [<time end>, <time start>] interval live

    Options:
        <time end>          Specify the earliest end time of the prev sessions that are live now
                            that should be taken offline. Specify as HHMM or none to indicate no prior
                            sessions, i.e., the sessions being started are the start of the day

        <time start>        Specify the latest start time of the next sessions that should be
                            made live. Specify as HHMM or none to indicate no following sessions,
                            i.e., the sessions being ended are the end of the day.
    """.format(sys.argv[0]))
    sys.exit(0)

database = schedule.Database(sys.argv[1], youtube=True, use_pickled_credentials=True)
# Fill in the computer stream key IDs
database.populate_stream_key_ids()
day = database.get_day(sys.argv[2])

time_end = None
if sys.argv[3].lower() != "none":
    time_end = datetime(schedule.CONFERENCE_YEAR, day.month, day.day,
            hour=int(sys.argv[3][0:2]), minute=int(sys.argv[3][2:4]), tzinfo=schedule.conf_tz)
else:
    time_end = datetime(schedule.CONFERENCE_YEAR, day.month, day.day,
            hour=0, minute=1, tzinfo=schedule.conf_tz)

time_start = None
if sys.argv[4].lower() != "none":
    time_start = datetime(schedule.CONFERENCE_YEAR, day.month, day.day,
            hour=int(sys.argv[4][0:2]), minute=int(sys.argv[4][2:4]), tzinfo=schedule.conf_tz)   
else:
    time_start = datetime(schedule.CONFERENCE_YEAR, day.month, day.day,
            hour=23, minute=0, tzinfo=schedule.conf_tz)   

print("Ending broadcasts whose sessions end in the interval [{}, {}]".format(time_end, time_start))
print("Advancing streams to broadcasts whose sessions start in the interval [{}, {}]".format(time_end, time_start))

end_sessions = []
start_sessions = []
for k, v in day.get_sessions(False).items():
    if not v.is_livestreamed():
        print(f"Skipping non-livestreamed session {v.event_session_title()}")
        continue

    time = v.session_time()
    if time[1] >= time_end and time[1] <= time_start:
        end_sessions.append(v)
    elif time[0] >= time_end and time[0] <= time_start:
        start_sessions.append(v)

print("=" * 10 + "\nPreview:")
print("Will end:")
for s in end_sessions:
    print(s.event_session_title())
    print("-----")

print("Will start:")
for s in start_sessions:
    print(s.event_session_title())
    print("-----")

print("=" * 10)

ok = input("Proceed? (y/n): ")
if ok == "n":
    print("Cancelling")
    sys.exit(0)

print("=" * 10 + "\nEnding sessions:")
for s in end_sessions:
    print(s.event_session_title())
    s.stop_streaming()
    non_consent_text = "Does not consent to video recording, Will edit out in post"
    if non_consent_text in s.special_notes():
        print("Make video {} private, non-consenting presentation".format(
            s.timeslot_entry(0, "Youtube Broadcast").value))
    print("-----")

print("=" * 10 + "\nStarting sessions:")
for s in start_sessions:
    print(s.event_session_title())
    s.start_streaming()
    print("-----")

# Annoying but have to run bot to post the starting/ending messages
client = discord.Client()
@client.event
async def on_ready():
    embed = schedule.base_discord_embed()
    embed["title"] = "The session has ended"

    for s in end_sessions:
        if not s.has_discord_channel():
            continue
        guild_id, channel_id = s.discord_ids()
        guild = [g for g in client.guilds if str(g.id) == guild_id][0]
        channel = [c for c in guild.text_channels if str(c.id) == channel_id]
        if len(channel) > 0:
            embed["description"] = f"Thanks for attending {s.event_session_title()}!"
            await channel[0].send(embed=discord.Embed.from_dict(embed))

    embed["title"] = "The next session will begin soon"
    embed["description"] = ""
    for s in start_sessions:
        if not s.has_discord_channel():
            continue
        guild_id, channel_id = s.discord_ids()
        guild = [g for g in client.guilds if str(g.id) == guild_id][0]
        channel = [c for c in guild.text_channels if str(c.id) == channel_id]
        if len(channel) > 0:
            await channel[0].send(embed=discord.Embed.from_dict(embed))
            session_start_info = await channel[0].send(embed=discord.Embed.from_dict(s.discord_embed_dict()))
            await session_start_info.pin()

    print("Start/End messages sent, hit Ctrl-C to kill the bot")

client.run(database.auth.discord["bot_token"])

