import sys
import pprint
import re
import os

import core.schedule as schedule

USAGE = """
./populate_poster_info.py <schedule_db.xlsx> <poster root dir> <event prefix>

Posters for the event should be under <video root dir>/<event prefix>
"""

if len(sys.argv) != 4:
    print(USAGE)
    sys.exit(1)

schedule_db = schedule.Database(sys.argv[1])
all_poster_root = os.path.normpath(sys.argv[2])
poster_root_path = os.path.join(all_poster_root, sys.argv[3])

match_poster = re.compile(".*_[pP]oster.pdf")
match_image = re.compile(".*_[iI]mage.*")
# Folks may not be great about following the naming prefix well,
# e.g. <prefix>-ID vs. <prefix>_ID , so just take the first number we get
# as the paper ID
match_id = re.compile(".*[^0-9]([0-9]+)[^0-9].*\\..*")
match_prefix = re.compile("([a-z4\\-]+)-\\d+")

poster_assets = {}
# Collect all the videos, subtitle, image and image caption info for this event indexed by UID
print(f"Collecting all assets under {poster_root_path}")
for path, dirs, files in os.walk(poster_root_path):
    for f in files:
        if f[0] == ".":
            continue

        ext = os.path.splitext(f)[1]
        if ext == ".json" or ext == ".zip" or ext == ".xlsx" or ext == ".txt":
            continue

        filename = os.path.join(path, f)
        relpath = os.path.relpath(filename, start=all_poster_root)

        paper_id_m = match_id.match(f)
        if not paper_id_m:
            print(f"File {filename} does not have a correct ID!?")
            sys.exit(1)

        poster_uid = sys.argv[3] + "-" + paper_id_m.group(1)
        if not poster_uid in poster_assets:
            poster_assets[poster_uid] = {
                "output": False   
            }

        m = match_poster.match(f)
        if m:
            poster_assets[poster_uid]["poster"] = relpath
            continue

        m = match_image.match(f)
        if m:
            poster_assets[poster_uid]["image"] = relpath
            caption_file = os.path.splitext(filename)[0] + ".txt"
            try:
                if os.path.isfile(caption_file):
                    with open(caption_file, "r") as f:
                        poster_assets[poster_uid]["caption"] = f.read()
            except:
                print(f"Failed to load caption {caption_file}")


# Iterate through the schedule and find each paper and populate its video, subtitles, image and caption info
poster_info = schedule_db.workbook.get_table("posters")
for r in poster_info.items():
    if not r["Event ID"].value:
        break
    poster_uid = r["Event ID"].value + "-" + str(r["ID"].value)
    if poster_uid in poster_assets:
        poster_info = poster_assets[poster_uid]
        if not "poster" in poster_info:
            print(f"No poster PDF was foud for {poster_uid}")
            continue
        
        r["PDF File"].value = poster_info["poster"]

        if "image" in poster_info:
            r["Image File"].value = poster_info["image"]
        if "caption" in poster_info:
            r["Summary"].value = poster_info["caption"]

        poster_assets[poster_uid]["output"] = True

        schedule_db.save("populated_poster_info_out.xlsx")
    else:
        print(f"No poster found for {poster_uid}")

# Make sure we matched up all the videos we found
for k, v in poster_assets.items():
    if not v["output"]:
        print(f"ERROR: Assets for UID {k} were not used! Presentation is missing or matching failed")
        pprint.pprint(v)


