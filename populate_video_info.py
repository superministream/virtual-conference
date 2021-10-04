import sys
import pprint
import re
import os
import pymediainfo

import core.schedule as schedule

USAGE = """
./populate_paper_info.py <schedule_db.xlsx> <video root dir> <event prefix>

Videos for the event should be under <video root dir>/<event prefix>
"""

if len(sys.argv) != 4:
    print(USAGE)
    sys.exit(1)

schedule_db = schedule.Database(sys.argv[1])
all_video_root = os.path.normpath(sys.argv[2])
video_root_path = os.path.join(all_video_root, sys.argv[3])

match_presentation = re.compile(".*_[pP]resentation.*")
match_image = re.compile(".*_[iI]mage.*")
# Folks may not be great about following the naming prefix well,
# e.g. <prefix>-ID vs. <prefix>_ID , so just take the first number we get
# as the paper ID
match_id = re.compile(".*[^0-9]([0-9]+)[^0-9].*\\..*")
match_prefix = re.compile("([a-z4\\-]+)-\\d+")

paper_assets = {}
# Collect all the videos, subtitle, image and image caption info for this event indexed by UID
print(f"Collecting all assets under {video_root_path}")
for path, dirs, files in os.walk(video_root_path):
    if "sv_assignments" in path:
        print(f"skipping {path}")
        continue
    for f in files:
        if f[0] == ".":
            continue

        ext = os.path.splitext(f)[1]
        if ext == ".json" or ext == ".zip" or ext == ".xlsx" or ext == ".txt":
            continue

        filename = os.path.join(path, f)
        relpath = os.path.relpath(filename, start=all_video_root)

        paper_id_m = match_id.match(f)
        if not paper_id_m:
            print(f"File {filename} does not have a correct ID!?")
            sys.exit(1)

        paper_uid = sys.argv[3] + "-" + paper_id_m.group(1)
        if not paper_uid in paper_assets:
            paper_assets[paper_uid] = {
                "output": False   
            }

        m = match_presentation.match(f)
        if m:
            mi = pymediainfo.MediaInfo.parse(filename)
            video_track = len([t for t in mi.tracks if t.track_type == "Video"]) != 0
            if not video_track:
                continue

            paper_assets[paper_uid]["video"] = relpath

            srt_file = os.path.splitext(filename)[0] + ".srt"
            sbv_file = os.path.splitext(filename)[0] + ".sbv"
            if os.path.isfile(srt_file):
                paper_assets[paper_uid]["subtitles"] = os.path.splitext(relpath)[0] + ".srt"
            elif os.path.isfile(sbv_file):
                paper_assets[paper_uid]["subtitles"] = os.path.splitext(relpath)[0] + ".sbv"
            continue

        m = match_image.match(f)
        if m:
            paper_assets[paper_uid]["image"] = relpath
            caption_file = os.path.splitext(filename)[0] + ".txt"
            try:
                if os.path.isfile(caption_file):
                    with open(caption_file, "r") as f:
                        paper_assets[paper_uid]["caption"] = f.read()
            except:
                print(f"Failed to load caption {caption_file}")


# Iterate through the schedule and find each paper and populate its video, subtitles, image and caption info
days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
for d in days:
    day_info = schedule_db.get_day(d)
    sessions = day_info.get_sessions(False)

    for k, v in sessions.items():
        for i in range(v.num_timeslots()):
            uid = v.timeslot_entry(i, "UID").value
            if not uid:
                continue

            title = v.timeslot_entry(i, 'Time Slot Title').value
            if not uid in paper_assets:
                m = match_prefix.match(uid)
                if not m:
                    print(f"UID {uid} doesn't match the UID pattern!")
                    sys.exit(1)

                prefix = m.group(1)
                if prefix == sys.argv[3]:
                    print(f"No presentation video was found for {title}, UID: {uid}")
                continue

            if not "video" in paper_assets[uid]:
                print(f"No presentation video was found for {title}, UID: {uid}")
                continue

            v.timeslot_entry(i, "Video File").value = paper_assets[uid]["video"]
            if "subtitles" in paper_assets[uid]:
                v.timeslot_entry(i, "Subtitles File").value = paper_assets[uid]["subtitles"]

            if "image" in paper_assets[uid]:
                v.timeslot_entry(i, "Preview Image File").value = paper_assets[uid]["image"]
            if "caption" in paper_assets[uid]:
                v.timeslot_entry(i, "Image Caption").value = paper_assets[uid]["caption"]

            paper_assets[uid]["output"] = True

            schedule_db.save("populate_video_info_out.xlsx")

# Make sure we matched up all the videos we found
for k, v in paper_assets.items():
    if not v["output"]:
        print(f"ERROR: Assets for UID {k} were not used! Presentation is missing or matching failed")
        pprint.pprint(v)

