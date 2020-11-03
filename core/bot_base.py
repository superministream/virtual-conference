import re
from datetime import timezone, datetime, timedelta

match_zoom_link = re.compile("https:\/\/.*\.zoom\.us\/j\/.*")

def parse_youtube_time(time):
    # If a suffix in milliseconds was included, remove it
    if "." in time:
        t = time.split(".")
        time = t[0] + "Z"
    # Youtube times are all UTC
    return datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

