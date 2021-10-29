import sys

import core.excel_db as excel_db
import core.schedule as schedule

if len(sys.argv) != 3:
    print("Usage: ./populate_ff_links.py <ff_sheet.xlsx> <database.xlsx>")
    sys.exit(1)

ff_sheet = excel_db.open(sys.argv[1]).get_table("VIS 2021")
database = schedule.Database(sys.argv[2])

# Get a map of paper uid -> FF link
paper_info = {}
for r in ff_sheet.items():
    ff_link = r["Video URL"].value
    if not ff_link:
        continue
    uid = r["UID"].value
    paper_info[uid] = {
        "ff_link": ff_link
    }

# Now run through the conference schedule and populate this info for each paper
for d in ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]:
    print(d)
    day = database.get_day(d)
    sessions = day.get_sessions(False)
    for k, v in sessions.items():
        for i in range(v.num_timeslots()):
            # All papers will have a UID
            uid = v.timeslot_entry(i, "UID").value
            if uid and uid in paper_info:
                v.timeslot_entry(i, "FF Link").value = paper_info[uid]["ff_link"]

database.save("populate_ff_links_out.xlsx")

