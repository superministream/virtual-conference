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

def getNextAvailableMachine(computers, time):
    for computer_id in computers.keys():
        avail_at, pc_id = computers[computer_id]
        if(avail_at <= time):
            return pc_id
    return None

database = schedule.Database(sys.argv[1], None)

day = database.get_day(sys.argv[2])
sessions = day.get_sessions(False)

event_dict = {}

computer_dict = {}
for c in database.computers.items():
    # All computers are initially marked as available starting at midnight
    avail_at = datetime(schedule.CONFERENCE_YEAR, day.month, day.day, hour=0, minute=1, tzinfo=schedule.conf_tz)
    # We also include the ID as a tiebreaker for when all the computers have the same time,
    # since the dicts are not comparable
    computer_dict[c["ID"].value] = (avail_at, c["ID"].value)

for k, v in sessions.items():
    session_time = v.session_time()
    if(v.event not in event_dict.keys()):
        event_dict[v.event] = getNextAvailableMachine(computer_dict, session_time[0] - v.setup_time())
    current_computer = event_dict[v.event]
    avail_at, pc_id = computer_dict[current_computer]
    # We need some setup time ahead of the session's start time to do A/V check with the presenters
    need_at = session_time[0] - v.setup_time()
    if(avail_at > need_at):
        print("Parallel session of same type?")
        current_computer = getNextAvailableMachine(computer_dict, session_time[0] - v.setup_time())
        avail_at, pc_id = computer_dict[current_computer]
    if avail_at > need_at:
        print("The next available computer isn't available until {},".format(schedule.format_time(avail_at)) + \
              " which is after the next session {} - {} that needs a computer for setup starting at: {}!"
              .format(v.event, v.name, schedule.format_time(need_at)))
        sys.exit(1)

    print("Session streams on computer {}".format(pc_id))
    print(v)
    print("Special notes: {}".format(v.special_notes()))
    print("------")
    # The computer is available again 10 minutes after this session ends for buffer
    avail_at = session_time[1] + timedelta(minutes=10)
    computer_dict[current_computer] = (avail_at, pc_id)

print("There are {} total sessions".format(len(sessions)))

