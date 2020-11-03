import srt
import os
import sys
import shutil
import webvtt
import re
from datetime import timedelta

# This script can adjust the subtitle timing in srt/sbv subtitles
# downloaded from YouTube, which often exports them with overlapping
# timing. The overlapping timing results in multiple subtitles appearing
# on screen in a hard to follow ordering. This script adjusts the timing
# so that only one subtitle is active at any time.

match_time = re.compile("(\d\d):(\d\d):(\d\d)\.(\d+)")

# Parse the timestamp and return hrs, mins, sec, milli
def parse_time_stamp(time):
    m = match_time.match(time)
    return timedelta(hours=int(m.group(1)), minutes=int(m.group(2)),
            seconds=int(m.group(3)), milliseconds=int(m.group(4)))

def format_time_stamp(time):
    hrs = int(time.total_seconds() / 3600)
    mins = int((time.total_seconds() % 3600) / 60)
    sec = int((time.total_seconds() % 3600) % 60)
    return "{:02d}:{:02d}:{:02d}.000".format(hrs, mins, sec)

def fix_subtitle_sequencing(filename):
    if os.path.isfile(filename + ".bk"):
        print("Not overwriting original backup for {}, skipping.".format(filename))
        return

    subs = None
    if os.path.splitext(filename)[1] == ".srt":
        subs = webvtt.from_srt(filename)
    elif os.path.splitext(filename)[1] == ".sbv":
        subs = webvtt.from_sbv(filename)

    # Adjust timing and stretch subtitles for fixing the live ones which
    # get messed up by Youtube
    if "--fix-live" in sys.argv:
        for i in range(len(subs)):
            start = parse_time_stamp(subs[i].start)
            start -= timedelta(seconds=8)
            if start < timedelta(hours=0, minutes=0, seconds=0, milliseconds=0):
                start = timedelta(hours=0, minutes=0, seconds=0, milliseconds=0)
            end = start + timedelta(seconds=4)
            subs[i].start = format_time_stamp(start)
            subs[i].end = format_time_stamp(end)

    for i in range(len(subs) - 1):
        end = parse_time_stamp(subs[i].end)
        next_start = parse_time_stamp(subs[i + 1].start)
        if end > next_start:
            subs[i].end = subs[i + 1].start

    if not "--dry" in sys.argv:
        shutil.copy(filename, filename + ".bk")
        out_srt = os.path.splitext(filename)[0] + ".srt"
        with open(out_srt, "w", encoding="utf8") as f:
            subs.write(f, format="srt")

video_root_path = os.path.normpath(sys.argv[1])
for path, dirs, files in os.walk(video_root_path):
    for f in files:
        if os.path.splitext(f)[1] == ".srt" or os.path.splitext(f)[1] == ".sbv":
            filepath = os.path.join(path, f)
            try:
                fix_subtitle_sequencing(filepath)
            except Exception as e:
                print("Failed to convert {}: {}".format(filepath, e))
