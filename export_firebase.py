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
    try:
        mi = pymediainfo.MediaInfo.parse(video_file)
        general_track = [t for t in mi.tracks if t.track_type == "General"][0]
        return general_track.to_data()["duration"] / 1000
    except Exception as e:
        print(f"Failed to get video length due to {e}")
        return 0


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
conference_days = ["demoday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
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

        if v.num_timeslots() == 1:
            session_type = v.timeslot_entry(0, "Time Slot Type").value
            if session_type == "Zoom Only" or session_type == "Gathertown Only":
                print(f"Skipping Zoom/Gathertown only session '{session_title}'")
                continue

        # Panel sessions can also have fast forwards
        ff_link = ""
        if event_type == "Panel" and v.timeslot_entry(0, "FF Link").value:
            ff_link = v.timeslot_entry(0, "FF Link").value
        
        ff_playlist = v.timeslot_entry(0, "FF Playlist").value

        room_id = v.timeslot_entry(0, "Computer").value
        room_info = database.get_computer(room_id)

        live_caption_url = v.timeslot_entry(0, "Live Captions URL").value

        room_str = f"room{room_id}"
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
            "notes": ", ".join(v.special_notes()),
            "has_live_captions": live_caption_url != None,
            "live_captions_url": live_caption_url,
            "zoom_url": v.timeslot_entry(0, "Zoom URL").value
        }

        # Each session begins with sponsor bumper
        bumper_video = room_info["Bumper Video"].value
        if bumper_video:
            bumper_video = schedule.match_youtube_id(bumper_video)

        session_info["stages"].append({
            "state": "WATCHING",
            "title": "Thanks to our Generous Sponsors!",
            "youtubeId": bumper_video
        })

        # Each session begins with the image preview of the session info
        session_info["stages"].append({
            "imageUrl": f"https://ieeevis.b-cdn.net/vis_2021/session_images/{session_id}.png",
            "state": "PREVIEW",
            "title": "The session will begin soon"
        })

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

        chairs = set()
        for i in range(v.num_timeslots()):
            if v.timeslot_entry(i, "Chair(s)").value:
                slot_chairs = v.timeslot_entry(i, "Chair(s)").value.split("|")
                for c in slot_chairs:
                    chairs.add(c)

            timeslot_title = v.timeslot_entry(i, "Time Slot Title").value
            timeslot_time = v.timeslot_time(i)
            timeslot_uid = v.timeslot_entry(i, "UID").value
            paper_uid = timeslot_uid
            if not timeslot_uid:
                event_prefix = v.timeslot_entry(i, "Event Prefix").value
                session_id = v.timeslot_entry(i, "Session ID").value
                timeslot_uid = f"{event_prefix}-{session_id}-t{i}"

            time_slot_info = {
                "title": timeslot_title,
                "state": "WATCHING",
                "contributors": ", ".join(v.timeslot_entry(i, "Contributor(s)").value.split("|")),
                "time_start": schedule.format_time_iso8601_utc(timeslot_time[0]),
                "time_end": schedule.format_time_iso8601_utc(timeslot_time[1]),
                "paper_uid": paper_uid if paper_uid else ""
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
            elif time_slot_type == "live":
                if livestream_youtubeid:
                    time_slot_info["youtubeId"] = livestream_youtubeid
                else:
                    print(f"No YouTube video found for live stream {timeslot_title} which should have one")
            elif time_slot_type == "gathertown":
                time_slot_info["state"] = "SOCIALIZING"
            else:
                print(f"Error! Unrecognized time slot type {time_slot_type}")
                sys.exit(1)

            session_info["stages"].append(time_slot_info)

            # Each talk is then followed by a live Q&A portion
            # TODO: Some events may want to play all the videos through then do Q&A after?
            # We can handle that or they can work it out with the technician
            # The Q&A portion then is just used to introduce the next talk directly
            qa_stage = {
                "live": True,
                "title": f"{timeslot_title} - Q&A",
                "state": "QA",
                "youtubeId": livestream_youtubeid,
                "slido_label": timeslot_uid,
                "notes": f"archive Q&A using slido label"
            }
            if video_length != 0:
                qa_stage["time_start"] = time_slot_info["time_end"]
                qa_stage["time_end"] = schedule.format_time_iso8601_utc(timeslot_time[1])

            session_info["stages"].append(qa_stage)

        session_info["chairs"] = ", ".join(chairs)

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
