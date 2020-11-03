import os
import sys
import json
import math
import asyncio
import requests
import discord
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import timezone, datetime, timedelta

import core.schedule as schedule

if "-h" in sys.argv or len(sys.argv) > 4:
    print("""Usage: {} <schedule sheet> <day> <time>

    Run the bot to handle polls and chat synchronization for sessions that overlap
    the time specified.

    Options:
        <schedule sheet>    The Excel sheet containing the day schedules
        <time>              A bot will be run to manage the chat for each session whose start/end
                            interval contains the time specified. Format as HHMM
    """.format(sys.argv[0]))
    sys.exit(0)

database = schedule.Database(sys.argv[1], youtube=True, use_pickled_credentials=True)
client = discord.Client()

day = database.get_day(sys.argv[2])
bot_time = datetime(schedule.CONFERENCE_YEAR, day.month, day.day,
        hour=int(sys.argv[3][0:2]), minute=int(sys.argv[3][2:4]), tzinfo=schedule.conf_tz)

channels = {}
videos = {}
video_stats = {}
prev_message = {}
last_send = datetime.now()

@client.event
async def on_ready():
    print("Logged in as {}".format(client.user))
    day = database.get_day(sys.argv[2])
    bot_time = datetime(schedule.CONFERENCE_YEAR, day.month, day.day,
            hour=int(sys.argv[3][0:2]), minute=int(sys.argv[3][2:4]), tzinfo=schedule.conf_tz)

    print("Bot handling sessions:")
    for k, v in day.get_sessions(False).items():
        time = v.session_time()
        if bot_time >= time[0] and bot_time <= time[1]:
            if not v.timeslot_entry(0, "Youtube Chat ID").value or not v.timeslot_entry(0, "Discord Link").value:
                print("No chat sync for {}".format(v.event_session_title()))
                continue

            guild_id, channel_id = v.discord_ids()
            guild = [g for g in client.guilds if str(g.id) == guild_id][0]
            for cat in guild.categories:
                channel = [c for c in guild.text_channels if str(c.id) == channel_id]
                if len(channel) > 0:
                    channel = channel[0]
                    break

            print(v.event_session_title())
            video_stats[v.youtube_broadcast_id()] = []
            videos[v.youtube_broadcast_id()] = v
            channels[v.youtube_broadcast_id()] = channel
            prev_message[v.youtube_broadcast_id()] = None

    client.loop.create_task(update_viewer_stats())

async def update_viewer_stats():
    global last_send
    while True:
        await asyncio.sleep(60)
        current_time = datetime.now()
        elapsed = current_time - last_send
        for v, views in video_stats.items():
            video = videos[v]
            stats = video.get_broadcast_statistics()
            if "concurrentViewers" in stats:
                viewers = int(stats['concurrentViewers'])
                views.append(viewers)
            else:
                continue

            if elapsed > timedelta(minutes=10):
                last_send = current_time
                fig, ax = plt.subplots(figsize=(8, 2))
                ax.plot(list(range(len(views))), views)
                ax.set_ylabel("Viewers")
                ax.set_ylim(ymin=0, ymax=np.max(video_stats[video.youtube_broadcast_id()]) + 10)
                ax.get_xaxis().set_ticks([])
                plot_filename = video.youtube_broadcast_id() + ".png"
                fig.savefig(plot_filename, bbox_inches="tight")
                with open(plot_filename, "rb") as fp:
                    if prev_message[v]:
                        await prev_message[v].delete()
                    prev_message[v] = await channels[v].send("Viewer statistics",
                            file=discord.File(fp))
                plt.close()
                os.remove(plot_filename)

client.run(database.auth.discord["bot_token"])

