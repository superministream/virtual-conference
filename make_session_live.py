import sys
import discord

import core.schedule as schedule

if "-h" in sys.argv or len(sys.argv) < 3:
    print("""Usage: {} <data sheet.xlsx> <session id> [--discord]

    Make the specified session live

    --discord   post in discord the session is live
    """.format(sys.argv[0]))
    sys.exit(0)

database = schedule.Database(sys.argv[1], youtube=True, use_pickled_credentials=True)
target_session_uid = sys.argv[2]

make_discord_post = "--discord" in sys.argv

# Fill in the computer stream key IDs
database.populate_stream_key_ids()

# Find the session and make it live
started_session = None
conference_days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
for d in conference_days:
    day = database.get_day(d)
    for k, v in day.get_sessions(False).items():
        session_name = v.timeslot_entry(0, "Session").value
        session_uid = v.timeslot_entry(0, "Session ID").value
        if session_uid == target_session_uid:
            print(f"Making session {session_uid} live! Session name '{session_name}'")
            v.start_streaming()
            started_session = v
            break

if not make_discord_post:
    sys.exit(0)

# Annoying but have to run bot to post the starting/ending messages
client = discord.Client()
@client.event
async def on_ready():
    embed = schedule.base_discord_embed()

    embed["title"] = "The next session will begin soon"
    embed["description"] = ""
    if not started_session.has_discord_channel():
        print("No discord channel for session")
        sys.exit(0)

    guild_id, channel_id = started_session.discord_ids()
    guild = [g for g in client.guilds if str(g.id) == guild_id][0]
    channel = [c for c in guild.text_channels if str(c.id) == channel_id]
    if len(channel) > 0:
        await channel[0].send(embed=discord.Embed.from_dict(embed))
        session_start_info = await channel[0].send(embed=discord.Embed.from_dict(started_session.discord_embed_dict()))
        await session_start_info.pin()

    print("Start/End messages sent, hit Ctrl-C to kill the bot")

client.run(database.auth.discord["bot_token"])

