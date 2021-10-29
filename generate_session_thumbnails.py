import sys
import os

import core.schedule as schedule

USAGE = """
generate_session_thumbnails.py <data sheet.xlsx> <thumbnail background> <font root dir> <asset root dir> <output_dir>
"""

if len(sys.argv) != 6:
    print(USAGE)
    sys.exit(1)

database = schedule.Database(sys.argv[1])
thumbnail_params = {
    "background": sys.argv[2],
    "fonts": {
        "bold": os.path.join(sys.argv[3], "bold-font.ttf"),
        "italic": os.path.join(sys.argv[3], "italic-font.ttf"),
        "regular": os.path.join(sys.argv[3], "regular-font.ttf"),
    },
    "asset_root_dir": sys.argv[4]
}
output_dir = sys.argv[5]

conference_days = ["demoday-sv", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
for d in conference_days:
    day = database.get_day(d)
    sessions = day.get_sessions(False)
    for k, v in sessions.items():
        session_id = v.timeslot_entry(0, "Session ID").value
        print(session_id)
        img = v.render_thumbnail(thumbnail_params)
        with open(os.path.join(output_dir, session_id + ".png"), "wb") as f:
            f.write(img.getbuffer())

