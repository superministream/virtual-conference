import sys
import time

import core.schedule as schedule

if len(sys.argv) < 3:
    print("Usage: {} <data sheet.xlsx> <day> [<logo_image.png>]".format(sys.argv[0]))
    sys.exit(1)

database = schedule.Database(sys.argv[1], email=True)

day = database.get_day(sys.argv[2])
sessions = day.get_sessions(False)

logo_image = None
if len(sys.argv) == 4:
    with open(sys.argv[3], "rb") as f:
        logo_image = f.read()

emails_sent = 0
for k, v in sessions.items():
    print(k)
    v.email_contributors(logo_image=logo_image)
    # We can do 14 emails per second with SES, but limit it a bit more
    emails_sent += 1
    if emails_sent % 14 == 0:
        time.sleep(2)

