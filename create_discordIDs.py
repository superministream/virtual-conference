import os
import sys
import pickle

if(not "DATA_FOLDER" in os.environ):
    print("You must set $DATA_FOLDER to a folder which contains the working data of this tool.")
    sys.exit(1)

if(len(sys.argv) != 4):
  print("Usage: {} ServerID SyncChannelID RoleChannelID".format(sys.argv[0]))

discordIDs = {"Server": int(sys.argv[1]),
              "SyncChannel": int(sys.argv[2]),
              "RoleChannel": int(sys.argv[3])}

f = open(os.environ["DATA_FOLDER"] + "/discordIDs.dat", "wb")
pickle.dump(discordIDs, f)
f.close()
