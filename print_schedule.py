import sys
import json
from datetime import datetime, timedelta
from heapq import heappush, heappop

import core.schedule as schedule

# This script will simulate scheduling the sessions on to the computers you're
# streaming with and print the resulting schedule. You can use this to validate
# the schedule set up before actually scheduling the event, e.g., to find a case
# where no computer is available to pick up a session.

if len(sys.argv) != 3:
    print("Usage: {} <data sheet.xlsx> <day>".format(sys.argv[0]))
    sys.exit(1)

database = schedule.Database(sys.argv[1], None)

day = database.get_day(sys.argv[2])
sessions = day.get_sessions(False)

# Now the tracks are set by the program schedule and more fixed. So instead
# of assigning computers they're already assigned and we just need to validate
# there aren't any conflicts caused by some typo or mistake in the sheet
computer_dict = {}
for c in database.computers.items():
    # All computers are initially marked as available starting at midnight
    avail_at = datetime(schedule.CONFERENCE_YEAR, day.month, day.day, hour=0, minute=1, tzinfo=schedule.conf_tz)
    # We also include the ID as a tiebreaker for when all the computers have the same time,
    # since the dicts are not comparable
    computer_dict[c["ID"].value] = (avail_at, c["ID"].value)

for k, v in sessions.items():
    session_time = v.session_time()
    session_track = v.get_track()
    avail_at, pc_id = computer_dict[session_track]
    # We need some setup time ahead of the session's start time to do A/V check with the presenters
    need_at = session_time[0] - v.setup_time()
    if avail_at > need_at:
        print(f"Session {v.event} - {v.name} is scheduled to start at {schedule.format_time(need_at)} on " + \
              f"track {session_track} but the Zoom/Track isn't available until {schedule.format_time(avail_at)}")
        sys.exit(1)

    print("Session streams on computer {}".format(pc_id))
    print(v)
    print("Special notes: {}".format(v.special_notes()))
    print("------")
    # The computer is available again 10 minutes after this session ends for buffer
    avail_at = session_time[1] + timedelta(minutes=10)
    computer_dict[session_track] = (avail_at, pc_id)

print("There are {} total sessions".format(len(sessions)))

