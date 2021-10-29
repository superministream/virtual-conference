import json
import sys
import os
import pymediainfo
import re
from enum import Enum, unique
from heapq import heappush, heappop
from zipfile import ZipFile

import core.excel_db as excel_db

# This script will let you easily build sets of zip files + Excel response sheets
# if you have a group of student volunteers who will be reviewing the videos for
# encoding errors. The script will also automatically check each video meets
# certain criteria (resolution, encoding, length).

match_presentation = re.compile("[^\\.].*_[pP]resentation.*")
#match_presentation = re.compile(".*\\.(mp4|mov|mkv)$")

USAGE ="""
Usage: assign_sv_videos.py already_assigned_list.json video_root_dir warnings_output.xlsx suffix [max talk length (minutes)]
"""

if len(sys.argv) < 5:
    print(USAGE)
    sys.exit(1)

max_talk_length = 1e20
if len(sys.argv) == 6:
    max_talk_length = int(sys.argv[5]) * 60

@unique
class EncodingWarning(Enum):
    CONTAINER = 1
    RESOLUTION = 2
    VIDEO_CODEC = 3
    AUDIO_CODEC = 4
    MISSING_SUBTITLES = 5
    CORRUPT = 6
    VIDEO_TOO_LONG = 7

    def is_error(self):
        return self == EncodingWarning.CORRUPT or self == EncodingWarning.VIDEO_TOO_LONG

class Video:
    def __init__(self, filepath, mediainfo):
        self.filepath = filepath
        self.has_track = {}
        for t in mediainfo.tracks:
            info = t.to_data()
            if t.track_type == "General":
                self.length = info["duration"] / 1000
                self.container = info["format"]
                self.has_track["General"] = True
            elif t.track_type == "Video":
                self.resolution = (info["width"], info["height"])
                self.video_codec = info["format"]
                self.has_track["Video"] = True
            elif t.track_type == "Audio":
                self.audio_codec = info["format"]
                self.has_track["Audio"] = True

    def get_warning(self):
        if len(self.has_track) != 3:
            return [EncodingWarning.CORRUPT]

        warnings = []
        if video.container != "MPEG-4":
            warnings.append(EncodingWarning.CONTAINER)
        if video.resolution != (1920, 1080):
            warnings.append(EncodingWarning.RESOLUTION)
        if video.video_codec != "AVC":
            warnings.append(EncodingWarning.VIDEO_CODEC)
        if video.audio_codec != "AAC":
            warnings.append(EncodingWarning.AUDIO_CODEC)
        # TODO: Videos should also be checked for a min length
        if video.length > max_talk_length:
            warnings.append(EncodingWarning.VIDEO_TOO_LONG)

        srt_file = os.path.splitext(self.filepath)[0] + ".srt"
        sbv_file = os.path.splitext(self.filepath)[0] + ".sbv"
        if not os.path.isfile(srt_file) and not os.path.isfile(sbv_file):
            warnings.append(EncodingWarning.MISSING_SUBTITLES)

        return warnings

    def __repr__(self):
        return "{} - {}s".format(self.filepath, self.length)

# Read JSON file containing list of all videos that
# have already been assigned so we can avoid redundant assignment
already_assigned = {}
if os.path.isfile(sys.argv[1]):
    with open(sys.argv[1], "r") as f:
        already_assigned = json.load(f)

warnings_db = None
if os.path.isfile(sys.argv[3]):
    warnings_db = excel_db.open(sys.argv[3])
else:
    warnings_db = excel_db.ExcelDb()

warnings_table = warnings_db.get_table("Sheet")
warnings_table.set_index(["video", "container", "resolution", "video_codec", "audio_codec", \
    "subtitles", "corrupted", "length", "critical", "emailed", "correction_due"])

# Walk through the current directories to find unassigned videos
# and get their lengths
unassigned_videos = []
video_root_path = os.path.normpath(sys.argv[2])
for path, dirs, files in os.walk(video_root_path):
    if "sv_assignments" in path:
        print(f"skipping {path}")
        continue
    for f in files:
        ext = os.path.splitext(f)[1]
        if ext == ".srt" or ext == ".sbv":
            continue
        m = match_presentation.match(f)
        if m:
            filename = os.path.join(path, f)
            relpath = os.path.relpath(filename, start=video_root_path)
            last_modified = os.path.getmtime(filename)
            if relpath not in already_assigned or already_assigned[relpath] < last_modified:
                if relpath in already_assigned:
                    print("File {} was updated, reassigning".format(filename))
                mi = pymediainfo.MediaInfo.parse(filename)
                video_track = len([t for t in mi.tracks if t.track_type == "Video"]) != 0
                if not video_track:
                    print(f"WARNING {filename} matched presentation but didn't have video track! Is it corrupt?")
                    continue

                video = Video(filename, mi)
                warnings = video.get_warning()
                warning_info = {
                    "video": relpath
                }
                if len(warnings) > 0:
                    print("{} has warnings".format(filename))
                    for w in warnings:
                        if w == EncodingWarning.CONTAINER:
                            warning_info["container"] = video.container
                        elif w == EncodingWarning.RESOLUTION:
                            warning_info["resolution"] = "{}x{}".format(video.resolution[0], video.resolution[1])
                        elif w == EncodingWarning.VIDEO_CODEC:
                            warning_info["video_codec"] = video.video_codec
                        elif w == EncodingWarning.AUDIO_CODEC:
                            warning_info["audio_codec"] = video.audio_codec
                        elif w == EncodingWarning.MISSING_SUBTITLES:
                            warning_info["subtitles"] = "MISSING"
                        elif w == EncodingWarning.CORRUPT:
                            warning_info["corrupted"] = "YES"
                        elif w == EncodingWarning.VIDEO_TOO_LONG:
                            warning_info["length"] = video.length / 60.0
                        if w.is_error():
                            warning_info["critical"] = "YES"

                    row = None
                    entry = warnings_table.find("video", relpath)
                    if len(entry) == 0:
                        row = warnings_table.append_row(warning_info)
                    else:
                        row = entry[0]
                        warnings_table.write_row(row, warning_info)

                    if "critical" in warning_info:
                        warnings_table.entry(row, "critical").style = "Bad"
                if "critical" in warning_info:
                    print("Critical encoding error for {}! Warnings = {}".format(filename, warnings))
                    continue
                unassigned_videos.append(video)

warnings_db.save(sys.argv[3])

# Divide the videos evenly among the N SVs and output a sheet for
# each one. The assigned videos will be copied into a zip file for the SV
# to download. Manually upload the sheet to google sheets for the SV and
# add a link to the shared zip file
print("Unassigned videos: {}".format(unassigned_videos))
if len(unassigned_videos) == 0:
    print("No unassigned videos")
    sys.exit(0)

total_time = sum([v.length for v in unassigned_videos])
print("Total Time to review: {}min".format(round(total_time / 60)))
num_volunteers = int(input("Assign between how many volunteers? "))
if num_volunteers == 0:
    sys.exit(0)

volunteers = []
for i in range(num_volunteers):
    heappush(volunteers, (0, i, []))

for v in unassigned_videos:
    task_time, volunteer, videos = heappop(volunteers)
    task_time += v.length
    videos.append(v)
    heappush(volunteers, (task_time, volunteer, videos))

index = ["Video File", "Subtitles File", "First Author", "Presenter", "Title", \
        "Playable in VLC? Y/N", "Video Errors", "Audio Errors", "Subtitle Errors"]

assignment_suffix = sys.argv[4]
for i in range(len(volunteers)):
    sv = volunteers[i]
    wb = excel_db.ExcelDb()
    ws = wb.get_table("Sheet")
    ws.set_index(index)

    task_length = 0
    with ZipFile("sv_assignment_{}_{}.zip".format(assignment_suffix, i), "w") as archive:
        for r in range(len(sv[2])):
            task_length += sv[2][r].length
            video_path = sv[2][r].filepath
            video_relpath = os.path.relpath(video_path, start=video_root_path)

            subtitles_path = None
            srt_path = os.path.splitext(sv[2][r].filepath)[0] + ".srt"
            sbv_path = os.path.splitext(sv[2][r].filepath)[0] + ".sbv"
            if os.path.isfile(srt_path):
                subtitles_path = srt_path
            elif os.path.isfile(sbv_path):
                subtitles_path = sbv_path

            subtitles_relpath = None
            if subtitles_path:
                subtitles_relpath = os.path.relpath(subtitles_path, start=video_root_path)
            info = {
                "Video File": video_relpath,
                "Subtitles File": subtitles_relpath
            }
            ws.append_row(info)
            archive.write(video_path, arcname=video_relpath)
            if subtitles_path:
                archive.write(subtitles_path, arcname=subtitles_relpath)

    # TODO: Generate row of "Needs escalation or fixing"
    last_row = ws.table.max_row
    ws.entry(last_row + 1, 1).value = "Total Task Time: {}minutes".format(round(task_length / 60))
    ws.entry(last_row + 1, 1).style = "Headline 1"

    ws.entry(last_row + 2, 1).value = "Instructions"
    ws.entry(last_row + 2, 2).value = "https://docs.google.com/document/d/1oyD0Cjt6tMdWIkZV3huNqDkWDJ_JIpGENmxqG0IsiVs/"
    ws.entry(last_row + 2, 1).style = "Headline 1"
    ws.entry(last_row + 2, 2).style = "Headline 1"

    ws.entry(last_row + 3, 1).value = "Videos Zip File:"
    ws.entry(last_row + 3, 1).style = "Headline 1"
    ws.entry(last_row + 3, 2).style = "Headline 1"

    wb.save("sv_assignment_{}_{}.xlsx".format(assignment_suffix, i))

for v in unassigned_videos:
    relpath = os.path.relpath(v.filepath, start=video_root_path)
    last_modified = os.path.getmtime(v.filepath)
    already_assigned[relpath] = last_modified

with open(sys.argv[1], "w") as f:
    f.write(json.dumps(already_assigned))

