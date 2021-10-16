import sys
from datetime import datetime, timedelta

import core.schedule as schedule

if len(sys.argv) < 3:
    print(f"Usage: {sys.argv[0]} <schedule.xlsx> <day>")
    sys.exit(1)

schedule_db = schedule.Database(sys.argv[1], zoom=True)
day = sys.argv[2]

computers = schedule_db.computers.items()
for c in computers:
    # Populate the info on the computer, then copy it to the day's schedule
    if c[f"Zoom URL {day}"].value:
        meeting_id = c[f"Zoom Meeting ID {day}"].value
        requested_url_expires = datetime.now() + timedelta(hours=2)
        # Convert to conference time zone
        requested_url_expires = requested_url_expires.astimezone(schedule.conf_tz)
        start_url = schedule.get_zoom_meeting_start_url(schedule_db.auth, meeting_id)

        c[f"Zoom Start URL {day}"].value = start_url
        c[f"Zoom Start URL Expires {day}"].value = schedule.format_time(requested_url_expires)

        schedule_db.save("populate_zoom_start_url_out.xlsx")

# Run through the schedule for the day and fill in the info
day_info = schedule_db.get_day(day)
sessions = day_info.get_sessions(False)
for k, v in sessions.items():
    session_computer = schedule_db.get_computer(v.get_track())
    for i in range(v.num_timeslots()):
        v.timeslot_entry(i, "Zoom Start URL").value = \
            session_computer[f"Zoom Start URL {day}"].value

        v.timeslot_entry(i, "Zoom Start URL Expires").value = \
            session_computer[f"Zoom Start URL Expires {day}"].value

    schedule_db.save("populate_zoom_start_url_out.xlsx")

