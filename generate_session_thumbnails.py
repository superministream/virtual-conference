import sys
import os

import core.schedule as schedule

USAGE = """
generate_session_thumbnails.py <data sheet.xlsx> <thumbnail background> <font root dir> <output_dir>
"""

if len(sys.argv) != 5:
    print(USAGE)
    sys.exit(1)

database = schedule.Database(sys.argv[1])
thumbnail_params = {
    "background": sys.argv[2],
    "bold_font": os.path.join(sys.argv[3], "title-font.ttf"),
    "regular_font": os.path.join(sys.argv[3], "body-font.ttf")
}
output_dir = sys.argv[4]

conference_days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
for d in conference_days:
    day = database.get_day(d)
    sessions = day.get_sessions(False)
    for k, v in sessions.items():
        session_id = v.timeslot_entry(0, "Session ID").value
        img = v.render_thumbnail(thumbnail_params)
        with open(os.path.join(output_dir, session_id + ".png"), "wb") as f:
            f.write(img.getbuffer())

