import sys
import json
import discord

import core.schedule as schedule
import core.auth as conf_auth

# This script is used to archive a discord channel to a JSON file
if len(sys.argv) != 2:
    print("Usage: {} <discord guild id>".format(sys.argv[0]))
    sys.exit(1)

discord_guild_id = int(sys.argv[1])

auth = conf_auth.Authentication()
client = discord.Client()

def user_to_json(user):
    return {
        "name": user.name,
        "display_name": user.display_name,
        "discriminator": user.discriminator
    }

def attachment_to_json(attachment):
    return {
        "width": attachment.width if attachment.width else 0,
        "height": attachment.height if attachment.height else 0,
        "url": attachment.url,
        "filename": attachment.filename
    }

def emoji_to_json(emoji):
    if type(emoji) == str:
        return {
            "type": "str",
            "emoji": emoji
        }
    if type(emoji) == discord.Emoji:
        return {
            "type": "discord.Emoji",
            "id": emoji.id,
            "name": emoji.name
            # The "urls" are discord.Asset objects which let you download
            # the emoji image from Discord's CDN
            #"url": emoji.url
        }
    if type(emoji) == discord.PartialEmoji:
        return {
            "type": "discord.PartialEmoji",
            "id": emoji.id,
            "name": emoji.name
            # The "urls" are discord.Asset objects which let you download
            # the emoji image from Discord's CDN
            #"url": emoji.url
        }

def reaction_to_json(reaction):
    return {
        "emoji": emoji_to_json(reaction.emoji),
        "count": reaction.count
    }

async def channel_messages_to_json(channel):
    messages = []
    async for m in channel.history(limit=None, oldest_first=True):
        messages.append({
            "author": user_to_json(m.author),
            "mentions": [user_to_json(user) for user in m.mentions],
            "content": m.content,
            "id": m.id,
            "attachments": [attachment_to_json(attach) for attach in m.attachments],
            "reactions": [reaction_to_json(react) for react in m.reactions],
            "created_at": schedule.format_time_iso8601_utc(m.created_at)
        })
    return messages

async def channels_to_json(channels):
    channel_json = []
    for c in channels:
        channel_json.append({
            "name": c.name,
            "id": c.id,
            "messages": await channel_messages_to_json(c)
        })
    return channel_json

@client.event
async def on_ready():
    archive = {}
    guild = [g for g in client.guilds if g.id == discord_guild_id][0]

    # Archive top level channels
    archive[0] = {
        "category_name": "",
        "id": 0,
        "channels": await channels_to_json(guild.text_channels)
    }

    for cat in guild.categories:
        archive[cat.id] = {
            "category_name": cat.name,
            "id": cat.id,
            "channels": await channels_to_json(cat.text_channels)
        }

    with open("discord_archive.json", "w", encoding="utf8") as f:
        json.dump(archive, f)

    print("Archive saved, hit Ctrl-C to kill the bot")

client.run(auth.discord["bot_token"])


