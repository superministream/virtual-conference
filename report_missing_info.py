import os
import sys
import shutil

import core.excel_db as excel_db

USAGE = """
Usage: report_missing_videos.py <datasheet.xlsx> <video root>
"""

# This script will run through the provided data sheet and report all
# cases where an entry is MISSING or a referenced video file cannot
# be found under the specific video root path

if len(sys.argv) < 3:
    print(USAGE)
    sys.exit(1)

video_root = sys.argv[2]
conference_days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
schedule_book = excel_db.open(sys.argv[1])

# Read the known slugs to record any missing ones
slug_sheet = schedule_book.get_table("session_slugs")
known_slugs = {}
for r in range(2, slug_sheet.table.max_row + 1):
    if not slug_sheet.entry(r, "Slug").value:
        continue
    known_slugs[slug_sheet.entry(r, "Slug").value] = {
        "Event": slug_sheet.entry(r, "Event").value,
        "Session": slug_sheet.entry(r, "Session").value
    }

missing_videos_index = ["Event", "Session", "Time Slot Title",
        "Video File", "Full Path", "Video Missing", "Subtitles Missing",
        "YT Video Missing", "YT Playlist Missing"]
missing_info_index = ["Time Slot", "Event", "Session", "Time Slot Title", "Items Missing"]

missing_items_db = excel_db.ExcelDb()
missing_slug_sheet = missing_items_db.create_table("missing_slugs", slug_sheet.index)
total_videos_missing = 0
total_subtitles_missing = 0
total_info_missing = 0
total_unknown_slugs = 0
for day in conference_days:
    sheet = schedule_book.get_table(day)
    missing_videos_sheet = missing_items_db.create_table(day + "-videos", missing_videos_index)
    missing_info_sheet = missing_items_db.create_table(day + "-info", missing_info_index)
    for r in range(3, sheet.table.max_row + 1):
        # Skip empty rows
        if not sheet.entry(r, "Time Slot").value:
            continue

        row_info = sheet.row(r)

        timeslot_type = row_info["Time Slot Type"].value

        video = row_info["Video File"].value
        if timeslot_type == "recorded" or video:
            event = row_info["Event"].value
            session = row_info["Session"].value
            title = row_info["Time Slot Title"].value
            # Default if we don't have the video file but this is a recorded talk, it's missing
            video_missing = True
            video_path = None
            if video:
                video_path = os.path.join(video_root, video)
                srt_path = os.path.join(video_root, os.path.splitext(video)[0] + ".srt")
                sbv_path = os.path.join(video_root, os.path.splitext(video)[0] + ".sbv")
                video_missing = not os.path.isfile(video_path)
            subtitles_missing = not os.path.isfile(srt_path) and not os.path.isfile(sbv_path)
            yt_video_uploaded = row_info["Youtube Video"].value != None
            yt_playlist_set = row_info["Youtube Playlist"].value != None

            if video_missing or subtitles_missing:
                if video_missing:
                    total_videos_missing += 1
                else:
                    total_subtitles_missing += 1
                missing_videos_sheet.append_row({
                    "Event": event,
                    "Session": session,
                    "Time Slot Title": title,
                    "Video File": video if video else "UNKNOWN/MISSING FILE!",
                    "Full Path": video_path if video_path else "UNKNOWN/MISSING FILE!",
                    "Video Missing": "YES" if video_missing else "",
                    "Subtitles Missing": "YES" if subtitles_missing else "",
                    "YT Video Missing": "YES" if not yt_video_uploaded else "",
                    "YT Playlist Missing": "YES" if not yt_playlist_set else "",
                })

        optional_image_assets = ["Session Logo", "Speaker Photo", "Custom Title Image"] 
        for image in optional_image_assets:
            image_file = row_info[image].value
            if image_file:
                image_path = os.path.join(video_root, image_file)
                if not os.path.isfile(image_path):
                    total_info_missing += 1
                    missing_info_sheet.append_row({
                        "Time Slot": row_info["Time Slot"].value,
                        "Event": row_info["Event"].value,
                        "Session": row_info["Session"].value,
                        "Time Slot Title": row_info["Time Slot Title"].value,
                        "Items Missing": image + " " + image_path
                    })

        # Check if any information is missing in this row and record it
        missing_info = []
        for k, v in row_info.items():
            if v.value and type(v.value) == str and "MISSING" in v.value:
                missing_info.append(k)
        if len(missing_info) > 0:
            total_info_missing += 1
            missing_info_sheet.append_row({
                "Time Slot": row_info["Time Slot"].value,
                "Event": row_info["Event"].value,
                "Session": row_info["Session"].value,
                "Time Slot Title": row_info["Time Slot Title"].value,
                "Items Missing": str(missing_info)
            })

        # Also report any slugs missing the session slugs list
        slug = row_info["Session ID"].value
        if slug and slug not in known_slugs and slug != "BREAK":
            if not missing_slug_sheet.find("Slug", slug):
                total_unknown_slugs += 1
                missing_slug_sheet.append_row({
                    "Slug": slug,
                    "Event": row_info["Event"].value,
                    "Session": row_info["Session"].value,
                })

missing_items_db.save("missing_items_db.xlsx")
print("There are {} total missing videos".format(total_videos_missing))
print("There are {} total missing subtitles".format(total_subtitles_missing))
print("There are {} total missing info items".format(total_info_missing))
print("There are {} total unknown slugs".format(total_unknown_slugs))

