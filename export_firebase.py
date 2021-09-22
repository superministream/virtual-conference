import sys
import shutil
import os
import json
from datetime import timedelta

import core.schedule as schedule

if len(sys.argv) < 2:
    print("Usage: {} <data sheet.xlsx>".format(sys.argv[0]))
    sys.exit(1)

database = schedule.Database(sys.argv[1])

rooms = {}
all_sessions = {}
#conference_days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
conference_days = ["tuesday"]
for d in conference_days:
    print(d)
    day = database.get_day(d)
    sessions = day.get_sessions(False)

    for k, v in sessions.items():
        session_time = v.session_time()
        event_prefix = v.timeslot_entry(0, "Event Prefix").value
        event = v.timeslot_entry(0, "Event").value
        session_title = v.timeslot_entry(0, "Session").value
        print(session_title)
        event_type = v.timeslot_entry(0, "Event Type").value
        session_id = v.timeslot_entry(0, "Session ID").value
        if not session_id:
            print("No Session ID for {} - {}".format(event, v.timeslot_entry(0, "Session").value))

        # Panel sessions can also have fast forwards
        ff_link = ""
        if event_type == "Panel" and v.timeslot_entry(0, "FF Link").value:
            ff_link = v.timeslot_entry(0, "FF Link").value
        
        ff_playlist = v.timeslot_entry(0, "FF Playlist").value

        track_id = v.timeslot_entry(0, "Computer").value
        track_info = database.get_computer(track_id)
        discord_channel_id = int(track_info["Discord Channel ID"].value)

        session_info = {
            "currentStatus": {
                "videoIndex": 1,
                "videoStartTimestamp": 0
            },
            "name": session_title,
            "session_id": session_id,
            "room": track_id,
            "slido": track_info["Slido"].value,
            "discord": track_info["Discord Channel ID"].value,
            "time_start": schedule.format_time_iso8601_utc(session_time[0]),
            "time_end": schedule.format_time_iso8601_utc(session_time[1]),
            "stages": []
        }

        # Each session begins with the image preview of the session info
        session_info["stages"].append({
            "imageUrl": session_id + ".png",
            "state": "PREVIEW",
            "title": "The session will begin soon"
        })

        bumper_id = track_info["Bumper Video"].value
        if bumper_id:
            bumper_id = schedule.match_youtube_id(bumper_id)

        # This is followed by a bumper video
        # TODO: I thought the order was bumper then preview?
        session_info["stages"].append({
            "youtubeId": bumper_id,
            "state": "SOCIALIZING",
            "title": f"The session '{session_title}' will begin soon"
        })

        livestream_youtubeid = None
        if v.timeslot_entry(0, "Youtube Broadcast").value:
            schedule.match_youtube_id(v.timeslot_entry(0, "Youtube Broadcast").value)


        # And a live opening by the chair or presenters
        session_info["stages"].append({
            "live": True,
            "title": "Opening",
            "state": "WATCHING",
            "youtubeId": livestream_youtubeid
        })

        for i in range(v.num_timeslots()):
            timeslot_title = v.timeslot_entry(i, "Time Slot Title").value
            timeslot_time = v.timeslot_time(i)
            time_slot_info = {
                "title": timeslot_title,
                "state": "WATCHING",
                "contributors": v.timeslot_entry(i, "Contributor(s)").value.split("|"),
                "time_start": schedule.format_time_iso8601_utc(timeslot_time[0]),
                "time_end": schedule.format_time_iso8601_utc(timeslot_time[1]),
            }

            time_slot_type = v.timeslot_entry(i, "Time Slot Type").value
            if not time_slot_type:
                time_slot_type = "recorded"

            if time_slot_type == "live":
                time_slot_info["live"] = True,

            if time_slot_type == "recorded":
                talk_video_url = v.timeslot_entry(i, "Youtube Video").value
                if talk_video_url:
                    time_slot_info["youtubeId"] = schedule.match_youtube_id(talk_video_url)
                else:
                    print(f"No YouTube video found for talk {timeslot_title} which should have a video")
            else:
                if livestream_youtubeid:
                    time_slot_info["youtubeId"] = livestream_youtubeid
                else:
                    print(f"No YouTube video found for live stream {timeslot_title} which should have one")

            session_info["stages"].append(time_slot_info)

            # Each talk is then followed by a live Q&A portion
            # TODO: Some events may want to play all the videos through then do Q&A after?
            # We can handle that or they can work it out with the technician
            # The Q&A portion then is just used to introduce the next talk directly
            session_info["stages"].append({
                "live": True,
                "title": f"{timeslot_title} - Q&A",
                "state": "WATCHING",
                "youtubeId": livestream_youtubeid
            })

        # The session concludes by returning to the bumper
        session_info["stages"].append({
            "youtubeId": bumper_id,
            "state": "SOCIALIZING",
            "title": "Thanks for attending!"
        })

        all_sessions[session_id] = session_info

with open("firebase_data.json", "w", encoding="utf8") as f:
    json.dump(all_sessions, f, indent=4)
