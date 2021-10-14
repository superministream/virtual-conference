import sys
import pprint
import os

import core.schedule as schedule
import core.excel_db as excel_db

USAGE = """
./populate_presenter_info.py <schedule_db.xlsx> <presneter info sheet>
"""

if len(sys.argv) != 3:
    print(USAGE)
    sys.exit(1)

schedule_db = schedule.Database(sys.argv[1])
presenters_db = excel_db.open(sys.argv[2]).get_table("Sheet1")

# Iterate through the schedule and search for presenting author info in the presenters_db
days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
for d in days:
    day_info = schedule_db.get_day(d)
    sessions = day_info.get_sessions(False)

    for k, v in sessions.items():
        for i in range(v.num_timeslots()):
            uid = v.timeslot_entry(i, "UID").value
            if not uid:
                continue

            presenter_row = presenters_db.find_if(lambda r: r["paper id"].value == uid)
            if len(presenter_row) == 0:
                continue

            presenter = presenters_db.row(presenter_row[0])
            print(f"Updating presenter info for {uid}")
            v.timeslot_entry(i, "Contributor(s)").value = presenter["presenter name"].value
            v.timeslot_entry(i, "Contributor Email(s)").value = presenter["presenter email"].value

schedule_db.save("populate_presenter_info_out.xlsx")

