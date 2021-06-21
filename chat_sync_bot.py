import os
import sys
import json
import asyncio
import math
import discord
import re
from datetime import timezone, datetime, timedelta
from googleapiclient.errors import HttpError

import core.schedule as schedule
import core.bot_base as base

if(not "DATA_FOLDER" in os.environ):
    print("You must set $DATA_FOLDER to a folder which contains the working data of this tool.")
    sys.exit(1)

class Bot:
    # Create a bot to manage polls and sync the chat between the youtube and discord chats
    def __init__(self, youtube_chat_id, youtube, discord_channel, discord):
        self.youtube_chat_id = youtube_chat_id
        self.youtube = youtube
        self.discord_channel = discord_channel
        self.discord = discord
        self.polls = []
        self.last_filter_read = None
        self.filter_users = self.get_filter_users()
        if self.youtube:
            self.discord.loop.create_task(self.poll_youtube_chat())

    def get_filter_users(self):
        # The user discriminators to not sync
        file_name = os.environ["DATA_FOLDER"] + "/chat_sync_filter_users.json"
        if not os.path.isfile(file_name):
            return []

        new_users = self.last_filter_read == None or os.path.getmtime(file_name) > self.last_filter_read
        if new_users:
            with open(file_name, "r") as f:
                self.filter_users = json.load(f)
            self.last_filter_read = os.path.getmtime(file_name)
            print("Got new filter users {}".format(self.filter_users))
        return self.filter_users

    async def on_discord_message(self, msg):
        filter_users = self.get_filter_users()
        if msg.author.name + msg.author.discriminator in filter_users:
            print("Filtering message by {}".format(msg.author.name))
            return
        # Also check if anyone mentioned is in the filter list
        for mention in msg.mentions:
            if mention.name + mention.discriminator in filter_users:
                print("Filtering message by {} which mentioned {}".format(msg.author.name,
                    mention.name))
                return
        # Don't sync Zoom URLs back to Youtube's public chat
        if not base.match_zoom_link.search(msg.content) and not msg.content.startswith("-") \
            and not msg.content.startswith("> -"):
                self.send_youtube_message("(Discord) " + msg.author.display_name, msg.content)

    # Async method to poll the youtube chat for new messages
    async def poll_youtube_chat(self):
        bot_start = datetime.now(tz=timezone.utc)
        await self.discord.wait_until_ready()
        chat = self.youtube.liveChatMessages().list(
            liveChatId=self.youtube_chat_id,
            part="snippet,authorDetails",
        ).execute()
        next_page_token = None
        while True:
            # Quit if we're disconnected from Discord
            if self.discord.is_closed():
                break

            new_youtube_messages = False
            for msg in chat["items"]:
                m = msg["snippet"]

                # Skip messages sent before the bot was started, e.g. if we had to restart the bot
                msg_time = base.parse_youtube_time(m["publishedAt"])
                if msg_time < bot_start:
                    continue

                if m["hasDisplayContent"] and m["type"] == "textMessageEvent":
                    text = m["textMessageDetails"]["messageText"]
                    if not text.startswith("(Discord)") and not text.startswith("(PollBot)"):
                        new_youtube_messages = True
                        await self.on_youtube_message(text, msg["authorDetails"])

            # If there's no activity on the youtube side, slow down how frequently we poll with a max
            # slow down of 6min
            polling_interval = math.ceil(float(chat["pollingIntervalMillis"]) / 1000.0)
            next_page_token = chat["nextPageToken"]
            # We have a quota increase for the chat manager so we can poll at the best frequency
            await asyncio.sleep(polling_interval)
            chat = self.youtube.liveChatMessages().list(
                liveChatId=self.youtube_chat_id,
                part="snippet,authorDetails",
                pageToken=next_page_token
            ).execute()

    async def on_youtube_message(self, msg_text, author):
        await self.send_discord_message("(Youtube) " + author["displayName"], msg_text)

    async def send_discord_message(self, author, text):
        await self.discord_channel.send("{}: {}".format(author, text))

    async def send_discord_embed(self, embed):
        await self.discord_channel.send(embed=discord.Embed.from_dict(embed))

    def send_youtube_message(self, author, text):
        if not self.youtube:
            return
        # Youtube chat is more basic and just does single line messages, so
        # multiline messages get split up into multiple individual messages
        if "\n" in text:
            lines = text.split("\n")
            for l in lines:
                if len(l) == 0 or l.startswith("-") or l.startswith("> -"):
                    continue
                self.send_youtube_message(author, l)
            return

        # We can only send messages of up to 200 characts to youtube, so if the
        # message from Discord is longer we need to chunk it up
        # Also cap author names to be at most 35chars
        if len(author) > 35:
            author = author[0:35]
        messages = ["{}: {}".format(author, text)]
        if len(messages[0]) > 200:
            header_len = len("{} [XX/YY]: ".format(author))
            chunk_size = 200 - header_len
            chunk_count = int(math.ceil(len(messages[0]) / chunk_size))
            messages = []
            for i in range(0, chunk_count):
                start = i * chunk_size
                end = (i + 1) * chunk_size
                if i + 1 == chunk_count:
                    end = len(text)
                messages.append("{} [{}/{}]: {}".format(
                    author, i + 1, chunk_count, text[start:end]))

        for m in messages:
            try:
                resp = self.youtube.liveChatMessages().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "type": "textMessageEvent",
                            "liveChatId": self.youtube_chat_id,
                            "textMessageDetails": {
                                "messageText": m[0:199]
                            }
                        }
                    }
                ).execute()
            except HttpError as e:
                print("Error sending message '{}' to youtube: {}".format(m[0:199], e))
            except:
                e = sys.exc_info()[0]
                print("Error sending message '{}' to youtube: {}".format(m, e))


database = schedule.Database(sys.argv[1], youtube=True, use_pickled_credentials=True)
client = discord.Client()
bots = []

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

            youtube_chat_id = v.timeslot_entry(0, "Youtube Chat ID").value
            guild_id, channel_id = v.discord_ids()
            guild = [g for g in client.guilds if str(g.id) == guild_id][0]
            for cat in guild.categories:
                channel = [c for c in guild.text_channels if str(c.id) == channel_id]
                if len(channel) > 0:
                    channel = channel[0]
                    break
            print(v.event_session_title())
            await channel.send("The chat will now be synchronized bidirectionally with YouTube")
            # NOTE: You'll want to update this information with where your warn zoom links/nosync bot is watching for $nosync commands
            await channel.send("You can prevent synchronization by prefixing your message with the - character, or completely by typing $nosync in #youtube-sync-commands")
            bots.append(Bot(youtube_chat_id, database.auth.youtube, channel, client))

@client.event
async def on_message(msg):
    if msg.author == client.user:
        return

    channel_bot = [b for b in bots if b.discord_channel.id == msg.channel.id]
    if len(channel_bot) == 0:
        return

    await channel_bot[0].on_discord_message(msg)

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

client.run(database.auth.discord["bot_token"])

