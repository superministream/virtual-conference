import sys
import re
import os
import shutil
import json
import discord
from datetime import datetime, timedelta
from PIL import Image
from heapq import heappush, heappop

import core.schedule as schedule

if len(sys.argv) != 5:
    print("Usage: {} <data sheet.xlsx> <day> <video root dir> <output root>".format(sys.argv[0]))
    sys.exit(1)

def list_to_html(l):
    if len(l) == 0:
        return ""
    return "<ul>" + "</li>".join(["<li>" + x for x in l]) + "</li></ul>"

database = schedule.Database(sys.argv[1])
day = database.get_day(sys.argv[2])
data_dir = os.path.normpath(sys.argv[3])
output_root = os.path.normpath(sys.argv[4])

optional_images = {
    "Session Logo": "session_logo.png",
    "Speaker Photo": "keynote_speaker.png",
    "Custom Title Image": "custom_title_card.png"
}

sessions = day.get_sessions(False)
for k, v in sessions.items():
    session_title_text = ""
    presentations_text = ""
    current_presentation_text = ""
    chair_list = []
    chair_emails = []
    presenter_list = []
    presenter_emails = []
    presentation_list = []
    session_time = v.session_time()

    print(v.event_session_title())
    if v.timeslot_entry(0, "Event Type").value == "Tutorial":
        presenters = v.timeslot_entry(0, "Organizer(s)").value.replace("|", ", ")
        current_presentation_text = presenters
        session_title_text = v.title_card_title()
        presentations_text = v.title_card_schedule()
        for t in range(len(v.timeslots)):
            presentation_title = v.timeslot_entry(t, "Time Slot Title").value
            presenters = v.timeslot_entry(t, "Contributor(s)").value.replace("|", ", ")
            presentation_list.append("{} - {}".format(presenters, presentation_title))
            presenter_list.append(presenters)

            if v.timeslot_entry(t, "Contributor Email(s)").value:
                presenter_emails.append(v.timeslot_entry(t, "Contributor Email(s)").value.replace("|", ", "))
            else:
                presenter_emails.append("N/A")

            if v.timeslot_entry(t, "Chair(s)").value:
                chair = v.timeslot_entry(t, "Chair(s)").value.replace("|", ", ")
                if not chair in chair_list:
                    chair_list.append(chair)
                    chair_emails.append(v.timeslot_entry(t, "Chair Email(s)").value.replace("|", ", "))

        presenter_list.reverse()
        presentation_list.reverse()
        current_presentation_text = "\n".join(presentation_list)
    else:
        event = v.timeslot_entry(0, "Event").value
        session_name = v.timeslot_entry(0, "Session").value
        pretty_session_time = schedule.format_time_slot(session_time[0], session_time[1])
        pretty_session_time = pretty_session_time[0:2] + ":" + pretty_session_time[2:4] + \
                "-" + pretty_session_time[5:7] + ":" + pretty_session_time[7:9]
        session_title_text = v.title_card_title()
        presentations_text = v.title_card_schedule()
        for t in range(len(v.timeslots)):
            presentation_title = v.timeslot_entry(t, "Time Slot Title").value
            presenters = v.timeslot_entry(t, "Contributor(s)").value.replace("|", ", ")
            presentation_list.append("{} - {}".format(presenters, presentation_title))
            presenter_list.append(presenters)

            if v.timeslot_entry(t, "Contributor Email(s)").value:
                presenter_emails.append(v.timeslot_entry(t, "Contributor Email(s)").value.replace("|", ", "))
            else:
                presenter_emails.append("N/A")

            if v.timeslot_entry(t, "Chair(s)").value:
                chair = v.timeslot_entry(t, "Chair(s)").value.replace("|", ", ")
                if not chair in chair_list:
                    chair_list.append(chair)
                    chair_emails.append(v.timeslot_entry(t, "Chair Email(s)").value.replace("|", ", "))
        # OBS Chat Log mode takes the bottom-most line, so flip the order. Technician then just
        # deletes the bottom line of the file as the session progresses 
        presenter_list.reverse()
        presentation_list.reverse()
        current_presentation_text = "\n".join(presentation_list)

    # Check for any special notes
    special_notes = v.special_notes()

    #session_dir_name = re.sub("[\\\/:\*\?'\"<>|]", "", v.timeslot_entry(0, "Session").value)
    session_dir_name = v.timeslot_entry(0, "Computer").value
    session_subdir = os.path.normpath(sys.argv[2] + "/{}/{}/".format(schedule.format_time_slot(session_time[0], session_time[1]),
        session_dir_name))
    session_output_dir = os.path.join(output_root, session_subdir) + "/"
    os.makedirs(session_output_dir, exist_ok=True)

    with open(session_output_dir + "session_title.txt", "w", encoding="utf8") as f:
        f.write(session_title_text)

    with open(session_output_dir + "session_schedule.txt", "w", encoding="utf8") as f:
        f.write(presentations_text)

    with open(session_output_dir + "session_chair.txt", "w", encoding="utf8") as f:
        f.write(v.title_card_chair())

    with open(session_output_dir + "current_presentation.txt", "w", encoding="utf8") as f:
        f.write(current_presentation_text)

    with open(session_output_dir + "technician_dashboard.html", "w", encoding="utf8") as f:
        session_schedule = []
        for t in range(len(v.timeslots)):
            time = v.timeslot_entry(t, "Time Slot").value
            title = v.timeslot_entry(t, "Time Slot Title").value
            presentation_type = v.timeslot_entry(t, "Time Slot Type").value
            presenters = v.timeslot_entry(t, "Contributor(s)").value.replace("|", ", ")
            time_slot_info = "{} [{}] - <b>{}</b> presenting '{}'".format(time, presentation_type, presenters, title)
            if v.timeslot_entry(t, "Video File Name").value:
                time_slot_info += " ({})".format(os.path.basename(v.timeslot_entry(t, "Video File Name").value))
            session_schedule.append(time_slot_info)

        # Re-reverse the presenter list to be in order
        presenter_list.reverse()
        chair_html = list_to_html([n + " - " + e for n, e in zip(chair_list, chair_emails)])
        contributor_html = list_to_html([n + " - " + e for n, e in zip(presenter_list, presenter_emails)])
        organizer_html = ""
        if v.timeslot_entry(0, "Organizer(s)").value and v.timeslot_entry(0, "Organizer Email(s)").value:
            organizers = v.timeslot_entry(0, "Organizer(s)").value.split("|")
            organizer_emails = v.timeslot_entry(0, "Organizer Email(s)").value.split("|")
            organizer_html = "<h1>Organizers</h1>" + list_to_html([n for n in organizers]) + \
                    "<h2>Organizer Email(s)</h2>" + list_to_html([n for n in organizer_emails])

        f.write("""<html>
        <head>
        <title>Technician Dashboard</title>
        </head>
        <body>
        <h1>Schedule for {title}</h1>
        <ul>
        {session_schedule_html}
        </ul>
        Note: The playlist.m3u will play the recorded talk videos in order for you, you'll just step
        through the playlist. VLC starts videos paused to avoid starting them before you're ready
        and ends them by pausing on the last frame.
        <h1>Session Chair(s)</h1>
        {chairs}
        <h1>Contributors</h1>
        {contributors}
        {organizer_info}
        <h1>Zoom URL</h1>
        <p><a href="{zoom}">{zoom}</a></p>
        <h1>Discord Link</h1>
        <p><a href="{discord}">{discord}</a></p>
        <h1>YouTube Studio (for monitoring)</h1>
        <p><a href="{yt_studio}">{yt_studio}</a></p>
        <h1>Special Notes</h1>
        <p>{special_notes}</p>
        </body>
        <html>
        """.format(title=v.event_session_title(),
            session_schedule_html=list_to_html(session_schedule),
            chairs=chair_html,
            contributors=contributor_html,
            organizer_info=organizer_html,
            zoom=v.timeslot_entry(0, "Zoom URL").value,
            discord=v.timeslot_entry(0, "Discord Link").value,
            yt_studio=v.timeslot_entry(0, "Youtube Control Room").value,
            special_notes=list_to_html(special_notes)))

    in_videos = [v.timeslot_entry(i, "Video File Name").value for i in range(v.num_timeslots()) \
            if v.timeslot_entry(i, "Video File Name").value]
    out_videos = []
    for video in in_videos:
        src_path = os.path.join(data_dir, video)
        dest_path = os.path.join(session_output_dir, os.path.basename(video))
        if not os.path.isfile(src_path):
            print("Video {} is missing!".format(src_path))
            continue
        shutil.copy(src_path, dest_path)
        out_videos.append(os.path.basename(video))

        srt_path = os.path.splitext(src_path)[0] + ".srt"
        sbv_path = os.path.splitext(src_path)[0] + ".sbv"
        src_subtitles_path = None
        dest_subtitles_path = None
        if os.path.isfile(srt_path):
            src_subtitles_path = srt_path
            dest_subtitles_path = os.path.splitext(dest_path)[0] + ".srt"
        elif os.path.isfile(sbv_path):
            src_subtitles_path = sbv_path
            dest_subtitles_path = os.path.splitext(dest_path)[0] + ".sbv"
        else:
            print("No subtitles for {}!".format(src_path))
            continue
        shutil.copy(src_subtitles_path, dest_subtitles_path)

    if len(out_videos) > 0:
        with open(session_output_dir + "playlist.m3u", "w", encoding="utf8") as f:
            for video in out_videos:
                f.write(video + "\n")

    uses_optional_images = {}
    for t in range(len(v.timeslots)):
        for img_name, img_out in optional_images.items():
            if v.timeslot_entry(t, img_name).value:
                uses_optional_images[img_name] = v.timeslot_entry(t, img_name).value


    for img_name, img_out in optional_images.items():
        if img_name in uses_optional_images:
            src_path = os.path.join(data_dir, uses_optional_images[img_name])
            dest_path = os.path.join(session_output_dir, img_out)
            # OBS will be looking for a PNG, so convert it if it's not one
            if os.path.splitext(src_path)[1] != ".png":
                im = Image.open(src_path)
                im.save(dest_path)
            else:
                shutil.copy(src_path, dest_path)
    print("=====")

