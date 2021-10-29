import sys
import shutil
import os
import json
import ics
from PIL import Image
from datetime import timedelta

import core.schedule as schedule

if len(sys.argv) < 3:
    print("Usage: {} <data sheet.xlsx> <base dir> <out_dir> [--img] [--ics] [--pdf]".format(sys.argv[0]))
    sys.exit(1)

database = schedule.Database(sys.argv[1])
export_images = "--img" in sys.argv
export_ics = "--ics" in sys.argv
export_pdfs = "--pdf" in sys.argv
output_asset_dir = sys.argv[2]
output_dir = sys.argv[3]

if (export_ics or export_images) and not os.path.exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)

full_vis_calendar = ics.Calendar()
event_calendars = {}

paper_list = {}
all_sessions = {}
conference_days = ["demoday-sv", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
for d in conference_days:
    print(d)
    day = database.get_day(d)
    sessions = day.get_sessions(False)

    for k, v in sessions.items():
        session_time = v.session_time()
        event_prefix = v.timeslot_entry(0, "Event Prefix").value
        event = v.timeslot_entry(0, "Event").value
        session_title = v.timeslot_entry(0, "Session").value
        event_type = v.timeslot_entry(0, "Event Type").value
        session_id = v.timeslot_entry(0, "Session ID").value
        if not session_id:
            print("No Session ID for {} - {}".format(event, v.timeslot_entry(0, "Session").value))

        organizers = v.timeslot_entry(0, "Organizer(s)").value
        event_description = v.timeslot_entry(0, "Event Description").value
        event_url = v.timeslot_entry(0, "Event URL").value
        zoom_meeting = ""
        zoom_password = ""
        special_notes = v.special_notes()
        if event_type == "Meetup" or "Attendees in Zoom" in special_notes:
            zoom_meeting = v.timeslot_entry(0, "Zoom URL").value
            zoom_password = v.timeslot_entry(0, "Zoom Password").value

        discord_category = ""
        discord_channel = ""
        discord_channel_id = 0
        if v.has_discord_channel():
            discord_category = v.chat_category_name()
            discord_channel = v.chat_channel_name()
            discord_channel_id = v.discord_channel_id()

        # Panel sessions can also have fast forwards
        ff_link = ""
        if event_type == "Panel" and v.timeslot_entry(0, "FF Link").value:
            ff_link = v.timeslot_entry(0, "FF Link").value
        
        ff_playlist = v.timeslot_entry(0, "FF Playlist").value

        if export_ics:
            calendar = v.make_calendar()
            full_vis_calendar.events |= calendar.events

            if event_prefix != session_id:
                if event_prefix not in event_calendars:
                    event_calendars[event_prefix] = ics.Calendar()
                event_calendars[event_prefix].events |= calendar.events
            
            with open(os.path.join(output_dir, session_id + ".ics"), "w", encoding="utf8") as f:
                f.write(str(calendar))

        computer_info = database.get_computer(v.get_track())

        session_info = {
            "title": session_title,
            "session_id": session_id,
            "track": "room" + str(v.get_track()),
            "schedule_image": session_id + ".png",
            "chair": [],
            "organizers": organizers.split("|") if organizers else [],
            "time_start": schedule.format_time_iso8601_utc(session_time[0]),
            "time_end": schedule.format_time_iso8601_utc(session_time[1]),
            "discord_category": discord_category,
            "discord_channel": discord_channel,
            "discord_channel_id": discord_channel_id,
            "discord_link": computer_info["Discord Link"].value,
            "slido_link": v.get_slido_url(),
            "youtube_url": v.timeslot_entry(0, "Youtube Broadcast").value,
            "zoom_meeting": zoom_meeting,
            "zoom_password": zoom_password,
            "ff_link": ff_link,
            "ff_playlist": ff_playlist if ff_playlist else "",
            "gathertown_event": v.timeslot_entry(0, "Time Slot Type").value == "Gathertown Only",
            "time_slots": [],
        }

        chairs = set()
        for i in range(v.num_timeslots()):
            if v.timeslot_entry(i, "Chair(s)").value:
                slot_chairs = v.timeslot_entry(i, "Chair(s)").value.split("|")
                for c in slot_chairs:
                    chairs.add(c)

            contributors = v.timeslot_entry(i, "Contributor(s)").value

            timeslot_time = v.timeslot_time(i)
            time_slot_info = {
                "type": v.timeslot_entry(i, "Time Slot Type").value,
                "title": v.timeslot_entry(i, "Time Slot Title").value,
                "contributors": contributors.split("|") if contributors else "",
                "abstract": v.timeslot_entry(i, "Abstract").value,
                "time_start": schedule.format_time_iso8601_utc(timeslot_time[0]),
                "time_end": schedule.format_time_iso8601_utc(timeslot_time[1]),
            }

            uid = v.timeslot_entry(i, "UID").value
            if uid:
                time_slot_info["uid"] = uid

            talk_video_url = v.timeslot_entry(i, "Youtube Video").value
            if talk_video_url:
                time_slot_info["youtube_video_id"] = schedule.match_youtube_id(talk_video_url)

            session_info["time_slots"].append(time_slot_info)

            # All papers will have a UID
            # Note: we could also export all paper information by checking for Paper Presentations
            # event types
            # This will pick up just VIS paper presentations (full, short, cga)
            if uid:
                keywords = v.timeslot_entry(i, "Keywords").value
                authors = v.timeslot_entry(i, "Authors").value
                if not authors:
                    print("Authors for {} are missing!".format(v.timeslot_entry(i, "UID").value))

                image_name = v.timeslot_entry(i, "Preview Image File").value
                if image_name:
                    image_name = os.path.join(output_asset_dir, image_name)

                special_notes = v.timeslot_entry(i, "Special Notes").value
                if special_notes:
                    special_notes = special_notes.split("|")

                paper_award = ""
                if special_notes:
                    if "best" in special_notes:
                        paper_award = "best"
                    elif "honorable" in special_notes:
                        paper_award = "honorable"

                image_caption = v.timeslot_entry(i, "Image Caption").value
                external_pdf_link = v.timeslot_entry(i, "PDF Link").value
                pdf_file = v.timeslot_entry(i, "PDF File").value
                ff_link = v.timeslot_entry(i, "FF Link").value

                paper_list[uid] = {
                    "authors": authors.split("|") if authors else "MISSING",
                    "title": v.timeslot_entry(i, "Time Slot Title").value,
                    "session_id": v.timeslot_entry(i, "Session ID").value,
                    "abstract": v.timeslot_entry(i, "Abstract").value,
                    "keywords": keywords.split("|") if keywords else [],
                    "uid": uid,
                    "time_stamp": schedule.format_time_iso8601_utc(timeslot_time[0]),
                    "has_image": image_name != None,
                    "paper_award": paper_award,
                    "image_caption": image_caption if image_caption else "",
                    "external_paper_link": external_pdf_link if external_pdf_link else "",
                    "has_pdf": pdf_file != None,
                    "ff_link": ff_link if ff_link else ""
                }

                if image_name and export_images:
                    out_path = os.path.join(output_dir, uid + ".png")
                    try:
                        if image_name.endswith("png"):
                            shutil.copy(image_name, out_path)
                        else:
                            im = Image.open(image_name)
                            im.save(out_path)
                    except Exception as e:
                        print("Image {} failed due to {}".format(image_name, e))

                if export_pdfs and pdf_file:
                    pdf_file = os.path.join(output_asset_dir, pdf_file)
                    if not os.path.isfile(pdf_file):
                        print(f"Error! Failed to find poster PDF {pdf_file}")
                        continue
                    out_pdf_file = os.path.join(output_dir, f"{uid}.pdf")
                    shutil.copy(pdf_file, out_pdf_file)

        session_info["chair"] = list(chairs)
        if not event_prefix in all_sessions:
            long_name = v.timeslot_entry(0, "Event Long Name").value
            all_sessions[event_prefix] = {
                "event": event,
                "long_name": long_name if long_name else event,
                "event_type": event_type,
                "event_description": event_description if event_description else "",
                "event_url": event_url if event_url else "",
                "sessions": [session_info],
            }
        else:
            all_sessions[event_prefix]["sessions"].append(session_info)

# Also export posters
poster_table = database.workbook.get_table("posters")
all_posters = {}
print("Exporting posters")
for r in poster_table.items():
    if not r["Event ID"].value:
        break

    poster_award = r["Award"].value
    if poster_award == None:
        poster_award = ""

    poster_uid = r["Event ID"].value + "-" + str(r["ID"].value)
    poster_info = {
        "title": r["Title"].value,
        "authors": r["Authors"].value.split("|"),
        "uid": poster_uid,
        "event": r["Event"].value,
        "discord_channel": r["Discord Channel ID"].value,
        "has_image": r["Image File"].value != None,
        "has_summary_pdf": r["Summary PDF"].value != None,
        "poster_award": poster_award
    }
    all_posters[poster_uid] = poster_info

    if export_pdfs:
        pdf_file = r["PDF File"].value
        if pdf_file:
            pdf_file = os.path.join(output_asset_dir, pdf_file)
            if not os.path.isfile(pdf_file):
                print(f"Error! Failed to find poster PDF {pdf_file}")
                continue

            out_pdf_file = os.path.join(output_dir, f"{poster_uid}.pdf")
            shutil.copy(pdf_file, out_pdf_file)

        summary_pdf_file = r["Summary PDF"].value
        if summary_pdf_file:
            summary_pdf_file = os.path.join(output_asset_dir, summary_pdf_file)
            if not os.path.isfile(summary_pdf_file):
                print(f"Error! Failed to find poster PDF {summary_pdf_file}")
                continue

            out_summary_pdf_file = os.path.join(output_dir, f"{poster_uid}-summary.pdf")
            shutil.copy(summary_pdf_file, out_summary_pdf_file)

    if export_images:
        image_file = r["Image File"].value
        if image_file:
            image_file = os.path.join(output_asset_dir, image_file)
            if not os.path.isfile(image_file):
                print(f"Error! Failed to find poster image file {image_file}")
                continue

            out_path = os.path.join(output_dir, f"{poster_uid}.png")
            try:
                if image_file.endswith("png"):
                    shutil.copy(image_file, out_path)
                else:
                    im = Image.open(image_file)
                    im.save(out_path)
            except Exception as e:
                print("Image {} failed due to {}".format(image_file, e))

if export_ics:
    with open(os.path.join(output_dir, schedule.CONFERENCE_NAME + ".ics"), "w", encoding="utf8") as f:
        f.write(str(full_vis_calendar))

    for k, v in event_calendars.items():
        with open(os.path.join(output_dir, k  + ".ics"), "w", encoding="utf8") as f:
            f.write(str(v))

with open("paper_list.json", "w", encoding="utf8") as f:
    json.dump(paper_list, f, indent=4)

with open("session_list.json", "w", encoding="utf8") as f:
    json.dump(all_sessions, f, indent=4)

with open("poster_list.json", "w", encoding="utf8") as f:
    json.dump(all_posters, f, indent=4)
