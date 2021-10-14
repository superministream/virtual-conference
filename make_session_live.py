import sys

import core.schedule as schedule

if "-h" in sys.argv or len(sys.argv) != 3:
    print("""Usage: {} <data sheet.xlsx> <session id>

    Make the specified session live
    """.format(sys.argv[0]))
    sys.exit(0)

database = schedule.Database(sys.argv[1], youtube=True, use_pickled_credentials=True)
target_session_uid = sys.argv[2]

# Fill in the computer stream key IDs
database.populate_stream_key_ids()

# Find the session and make it live
conference_days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
for d in conference_days:
    day = database.get_day(d)
    for k, v in day.get_sessions(False).items():
        session_name = v.timeslot_entry(0, "Session").value
        session_uid = v.timeslot_entry(0, "Session ID").value
        if session_uid == target_session_uid:
            print(f"Making session {session_uid} live! Session name '{session_name}'")
            v.start_streaming()
            break

