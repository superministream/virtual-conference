import sys
import pprint
import re
import os

import core.schedule as schedule

nonalphanumeric = re.compile("[^A-Za-z0-9]")

def make_normalized_title(title):
    if not title:
        return ""
    norm = nonalphanumeric.sub("", title)
    norm = norm.lower()
    if len(norm) > 64:
        return norm[0:64]
    return norm

USAGE = """
./populate_paper_info.py <schedule_db.xlsx> <PDF root dir>
"""

if len(sys.argv) != 3:
    print(USAGE)
    sys.exit(1)

schedule_db = schedule.Database(sys.argv[1])
pdf_root_path = os.path.normpath(sys.argv[2])

pdf_files = {}
# Collect all the videos, subtitle, image and image caption info for this event indexed by UID
print(f"Collecting all PDFs under {pdf_root_path}")
for path, dirs, files in os.walk(pdf_root_path):
    for f in files:
        basename = os.path.basename(f)
        title, ext = os.path.splitext(basename)
        if ext != ".pdf":
            continue

        filename = os.path.join(path, f)
        relpath = os.path.relpath(filename, start=pdf_root_path)
        pdf_files[make_normalized_title(title)] = {
            "path": "papers/" + relpath,
            "used": False
        }

# Iterate through the schedule and match up each PDF with its paper
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
            normtitle = make_normalized_title(title)
            if normtitle in pdf_files:
                pdf_file = pdf_files[normtitle]["path"]
                #print(f"Matched {title} to {pdf_file}")
                v.timeslot_entry(i, "PDF File").value = pdf_file 
                pdf_files[normtitle]["used"] = True

schedule_db.save("populate_pdf_info_out.xlsx")

# Make sure we matched up all the videos we found
for k, v in pdf_files.items():
    if not v["used"]:
        fname = v["path"]
        print(f"ERROR: PDF {fname} was not used! Slug {k}")
        pprint.pprint(v)


