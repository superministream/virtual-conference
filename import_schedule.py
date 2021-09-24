import sys
import os
import json
from datetime import timezone, datetime, timedelta

import core.schedule as schedule

if len(sys.argv) < 3:
    print("Usage: {} <data sheet.xlsx> <json schedule> <out.xlsx>".format(sys.argv[0]))
    sys.exit(1)

def parse_time(time_str):
    return datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def day_name_for_date(date):
    if date.day == 24:
        return "sunday"
    if date.day == 25:
        return "monday"
    if date.day == 26:
        return "tuesday"
    if date.day == 27:
        return "wednesday"
    if date.day == 28:
        return "thursday"
    if date.day == 29:
        return "friday"
    raise Exception("Unrecognized date!?")

schedule_json = None
with open(sys.argv[2], "r") as f:
    schedule_json = json.load(f)

# Find all sessions and sort them by date
all_sessions = []
for event_prefix, event in schedule_json.items():
    for session in event["sessions"]:
        session["event_prefix"] = event_prefix
        session["event"] = event["event"]
        session["session_id"] = event_prefix + "-" + session["session_id"]
        session["time_start"] = parse_time(session["time_start"])
        session["time_end"] = parse_time(session["time_end"])
        all_sessions.append(session)

all_sessions.sort(key=lambda s: s["time_start"])

database = schedule.Database(sys.argv[1])
session_tracks = database.workbook.get_table("session-tracks")
for session in all_sessions:
    session_start = session["time_start"].astimezone(tz=schedule.conf_tz)
    day = database.get_day(day_name_for_date(session_start))
    for slot in session["time_slots"]:
        track = session_tracks.find("Session ID", session["session_id"])
        if len(track) != 1:
            print(f"Error: No track or multiple found for session with id {session['session_id']}, title: {session['title']}")
            sys.exit(1)
        track = session_tracks.entry(track[0], "Track").value

        time_start = parse_time(slot["time_start"]).astimezone(tz=schedule.conf_tz)
        time_end = parse_time(slot["time_end"]).astimezone(tz=schedule.conf_tz)
        day.sheet.append_row({
            "Time Slot": schedule.format_time_slot(time_start, time_end),
            "Event": session["event"],
            "Event Prefix": session["event_prefix"],
            "Session ID": session["session_id"],
            "Session": session["title"],
            # Panels have an odd time slot title name in the JSON, so correct it here
            "Time Slot Title": slot["title"] if slot["title"] != "Organizers" else session["title"],
            "Authors": "|".join(slot["contributors"]),
            "Contributor(s)": "|".join(slot["contributors"]),
            "Chair(s)": "|".join(session["chair"]),
            "Computer": track
        })

database.save(sys.argv[3])

