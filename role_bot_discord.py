import sys
import re
import json
import discord
import os
import pickle

import core.auth as conf_auth
import core.bot_base as base

# This bot monitors the unlock channel and hands out roles. 
# This bot can be started at the beginning of the conference and left running the entire time.

if(not "DATA_FOLDER" in os.environ):
    print("You must set $DATA_FOLDER to a folder which contains the working data of this tool.")
    sys.exit(1)
    
f = open(os.environ["DATA_FOLDER"] + "/discordIDs.dat", "rb")
discordIDs = pickle.load(f)
f.close()

discord_server_id = discordIDs["Server"]
role_channel_id = discordIDs["RoleChannel"]

auth = conf_auth.Authentication()
client = discord.Client()

brute_force_protection_file_name = os.environ["DATA_FOLDER"] + "/brute_force_protection.dat"
# The keys of this dictionary should have the same name as the roles on your Discord.
token_file_names = {"Attendee": os.environ["DATA_FOLDER"] + "/Attendee_Tokens.txt", 
                    "Chair": os.environ["DATA_FOLDER"] + "/Chair_Tokens.txt",
                    "Speaker": os.environ["DATA_FOLDER"] + "/Speaker_Tokens.txt"}

@client.event
async def on_ready():
    guild = [g for g in client.guilds if g.id == discord_server_id][0]
    print("Role Bot ready.")

@client.event
async def on_message(msg):
    f = open(brute_force_protection_file_name, "rb")
    sender_dict = pickle.load(f)
    f.close()
    
    user_dict_id = msg.author.name + msg.author.discriminator
        
    if(msg.author == client.user):
        return

    if(msg.guild.id != discord_server_id or
       msg.channel.id != role_channel_id):
        return

    if(user_dict_id in sender_dict.keys()):
        if(sender_dict[user_dict_id] >= 3):
            await msg.author.send(content = "You tried to unlock too often. Please contact an administrator for help.")
            print("Brute Force Attempt by " + str(msg.author) + " blocked.")
            print()
            return

    print("Role requested by {}".format(msg.author.name))

    for group in token_file_names.keys():
        f = open(token_file_names[group], "r")
        tokens = f.readlines()
        f.close()
        if(msg.content + "\n" in tokens):
            print(str(group) + " token detected.")
            tokens.remove(msg.content + "\n")
            
            f = open(token_file_names[group], "w")
            f.writelines(tokens)
            f.close()
            
            role = discord.utils.get(msg.guild.roles, name = group)
            await msg.author.add_roles(role)
            await msg.author.send(content = "You received the role " + str(role) + ".")
            print(str(msg.author) + " got the role: " + str(role))
            print()
            return

    print("Token not detected.")
    print()
    if(user_dict_id in sender_dict.keys()):
        sender_dict[user_dict_id] += 1
    else:
        sender_dict[user_dict_id] = 1
    f = open(brute_force_protection_file_name, "wb")
    pickle.dump(sender_dict, f)
    f.close()

client.run(auth.discord["bot_token"])

