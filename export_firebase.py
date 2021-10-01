import sys
import shutil
import os
import json
from datetime import timedelta
import pymediainfo

import core.schedule as schedule

if len(sys.argv) < 3:
    print("Usage: {} <data sheet.xlsx> <video root dir>".format(sys.argv[0]))
    sys.exit(1)

def get_video_length(video_file):
    mi = pymediainfo.MediaInfo.parse(video_file)
    general_track = [t for t in mi.tracks if t.track_type == "General"][0]
    return general_track.to_data()["duration"] / 1000


database = schedule.Database(sys.argv[1])
video_root_dir = sys.argv[2]

rooms = {}
for c in database.computers.items():
    room_id = c["ID"].value
    room_str = f"room{room_id}"
    rooms[room_str] = {
        "slido": c["Slido Event"].value,
        "slido_room": c["Slido Room"].value,
        "discord": c["Discord Channel ID"].value,
        "name": c["Name"].value,
        "currentSession": ""
    }

all_sessions = {}
#conference_days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
conference_days = ["demoday"]
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

        room_str = f"room{track_id}"
        session_info = {
            "currentStatus": {
                "videoIndex": 0,
                "videoStartTimestamp": 0
            },
            "name": session_title,
            "session_id": session_id,
            "room": room_str,
            "time_start": schedule.format_time_iso8601_utc(session_time[0]),
            "time_end": schedule.format_time_iso8601_utc(session_time[1]),
            "stages": [],
            "special_notes": " ".join(v.special_notes())
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

        livestream_youtubeid = None
        if v.timeslot_entry(0, "Youtube Broadcast").value:
            livestream_youtubeid = schedule.match_youtube_id(v.timeslot_entry(0, "Youtube Broadcast").value)


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

            video_length = 0
            if time_slot_type == "recorded":
                talk_video = v.timeslot_entry(i, "Video File").value
                if talk_video:
                    video_length = get_video_length(os.path.join(video_root_dir, talk_video))
                    time_slot_info["video_length"] = video_length
                    talk_video_end = timeslot_time[0] + timedelta(seconds=video_length)
                    time_slot_info["time_end"] = schedule.format_time_iso8601_utc(talk_video_end)

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
            qa_stage = {
                "live": True,
                "title": f"{timeslot_title} - Q&A",
                "state": "QA",
                "youtubeId": livestream_youtubeid
            }
            if video_length != 0:
                qa_stage["time_start"] = time_slot_info["time_end"]
                qa_stage["time_end"] = schedule.format_time_iso8601_utc(timeslot_time[1])

            session_info["stages"].append(qa_stage)

        # The session concludes by returning to the bumper
        session_info["stages"].append({
            "state": "SOCIALIZING",
            "title": "Thanks for attending!"
        })

        all_sessions[session_id] = session_info

with open("firebase_data_sessions.json", "w", encoding="utf8") as f:
    json.dump(all_sessions, f, indent=4)

with open("firebase_data_rooms.json", "w", encoding="utf8") as f:
    json.dump(rooms, f, indent=4)
