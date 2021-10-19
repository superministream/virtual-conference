import sys
import time
from datetime import datetime, timedelta

import core.schedule as schedule

# Update the zoom start URLs in the schedule every 1.75hrs
# to keep them fresh. This is needed for the student volunteers
# so they can easily grab host if needed in a meeting, and because
# we don't have the long expiring start URLs since our user accounts
# are normal user accounts.

if len(sys.argv) < 3:
    print(f"Usage: {sys.argv[0]} <schedule in/out.xlsx> <day>")
    sys.exit(1)

schedule_file = sys.argv[1]
schedule_db = schedule.Database(schedule_file, zoom=True)
day = sys.argv[2]

while True:
    start_update = datetime.now()
    print(f"Updating Zoom URLs on {schedule.format_time(start_update)}")
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

            schedule_db.save(schedule_file)

    # Run through the schedule for the day and fill in the info
    day_info = schedule_db.get_day(day)
    sessions = day_info.get_sessions(False)
    for k, v in sessions.items():
        # The SV sheet refers to them as tracks so it's a bit easier for them to match up
        computer = v.timeslot_entry(0, "Track").value
        session_computer = schedule_db.get_computer(computer)
        for i in range(v.num_timeslots()):
            v.timeslot_entry(i, "Zoom Start URL").value = \
                session_computer[f"Zoom Start URL {day}"].value

            v.timeslot_entry(i, "Zoom Start URL Expires").value = \
                session_computer[f"Zoom Start URL Expires {day}"].value

        schedule_db.save(schedule_file)

    next_update = datetime.now() + timedelta(minutes=120)
    print(f"Update complete. Will refresh URLs at {schedule.format_time(next_update)}")
    # Wait for 2hr to update the URLs again, since they expire after 2hrs
    time.sleep(120 * 60)

