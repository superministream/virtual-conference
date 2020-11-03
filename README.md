# SuperMiniStream Virtual Conference

Scripts for managing scheduling and running a virtual conference that is live streamed to YouTube.
Live portions of the conference (Q&A, panels, live talks) take place over Zoom and are streamed
to YouTube. Attendees watch the conference on YouTube and ask questions or chat in Discord.
Each computer is assigned a single YouTube stream key, which is moved through the YouTube broadcasts
it is assigned to stream by a script.
The scripts expect your conference schedule to be formatted as shown
[here](https://docs.google.com/spreadsheets/d/1kKK0xCSkGw3JLcWwvhKxa2B9fydJbg3YZ6hU6XC0c_w/edit?usp=sharing), with one
sheet per day in your schedule Excel workbook.

# Documentation

The core scripts of interest for managing a virtual conference are `schedule_day.py`, `email_session_participants.py`,
`compile_session_assets.py`, and `advance_streams.py`. Additional scripts are provided for various bots that
can be run during the conference or utilities that can be helpful to have when organizing a virtual conference.

## Core Scheduling Scripts

You must configure the authentication information in `$SUPERMINISTREAM_AUTH_FILE` to
authenticate with the APIs used. The scripts use AWS's Simple Email Service for email,
the YouTube API to manage YouTube videos, a Discord bot for managing the Discord server
and a Zoom JWT app for creating the Zoom meetings. [Get in touch](https://www.superministream.com/)
if you have questions about setting up applications for using these APIs.
Note that if you're using your own Google API client to create YouTube broadcasts or upload videos
you [**must** undergo a YouTube API use audit](https://developers.google.com/youtube/v3/revision_history#release_notes_07_28_2020),
otherwise your videos will be flagged and made private.

### Schedule Day (`schedule_day.py`)

Schedule day is used to create the YouTube broadcasts, Zoom meetings, and Discord channels
for a day of conference sessions. It takes the Excel workbook containing your conference
schedule, the day to schedule, and the Discord guild ID to create the items for the day.
It also takes a path to an image file and path to a font directory to render thumbnail images
of the session schedule for each YouTube video. The thumbnail produced will look
[like this image](https://i.imgur.com/V0zKXgs.png). You can test creating the thumbnail by
calling `core.thumbnail.render_thumbnail` directly and saving out the returned BytesIO object as a PNG file.

```
./schedule_day.py <schedule sheet.xlsx> <day> <Discord guild ID> <thumbnail image> <font root dir>
```

### Email Session Participants (`email_session_participants.py`)

Email session participants is used to email the presenters, chairs, and organizers the session
information they need for the sessions they are taking part in. A single email is sent to all
participants in a session, containing the YouTube, Zoom Meeting, and Discord links.
You can optionally provide a logo image file to attach to the bottom of the email.

```
./email_session_participants.py <schedule sheet.xlsx> <day> [<logo image.png>]
```

### Compile Session Assets (`compile_session_assets.py`)

Compile session assets is used to build asset directories for the sessions run on each
computer. The output is a directory structure: `<day>/<time start>-<time end>/<computer ID>/`
containing the videos, technician dashboard with a summary of the session, and
text files for OBS Studio containing the session schedule.

```
./compile_session_assets.py <schedule sheet.xlsx> <day> <video root dir> <output root dir>
```

### Advance Streams (`advance_streams.py`)

Advance streams is used during the conference to manage binding the live streams from
each computer to the YouTube broadcast for the current time. It takes the time window
in which streams should be ending to be ended or starting to be started. 
The script takes a `[<time end>, <time start>]` time window, sessions that end in
this time window will be taken offline, while those that start in this window
will be made live.


```
./advance_streams.py <schedule sheet.xlsx> <day> <time end> <time start>

Advance the streams to the next broadcasts to be made live, and make those broadcasts live.
Will take offline the broadcasts that ended within the [<time end>, <time start>] interval
and make those starting within the [<time end>, <time start>] interval live

Options:
    <time end>          Specify the earliest end time of the prev sessions that are live now
                        that should be taken offline. Specify as HHMM or none to indicate no prior
                        sessions, i.e., the sessions being started are the start of the day

    <time start>        Specify the latest start time of the next sessions that should be
                        made live. Specify as HHMM or none to indicate no following sessions,
                        i.e., the sessions being ended are the end of the day.
```

## Discord Bots

There are three Discord bots included to provide various useful and optional functionality
to the conference.

### Discord and YouTube Chat Sync Bot (`chat_sync_bot.py`)

The chat sync bot unifies the conference chat platform between Discord and YouTube
by synchronizing the two chat platforms. The bot uses the YouTube chat ID and Discord
channel ID stored for each session in the sheet to synchronize the two chat platforms
for each session. Messages posted in the Discord channel are posted to the YouTube chat
for the live broadcast, while those posted in the YouTube chat for the broadcast
are posted back to Discord. The bot takes the schedule sheet, day, and time to run
for. The sessions whose time slot contains the specified time will have their
chat platforms synchronized.

```
./chat_sync_bot.py <schedule_sheet.xlsx> <day> <time>
```

**Note:** Some users found the bidirectional chat synchronization surprising,
and did not want their messages synchronized. Messages can be prefixed by `-` to
prevent single messages being synchronized, or when running the Monitor Discord
bot, users can type `$nosync` in your support channel to fully disable sync for their
messages and messages mentioning them.

### Monitor Discord Bot (`monitor_discord_bot.py`)

The monitor discord bot watches the Discord channel for Zoom links, to notify
authors that they should be sure to enable waiting rooms and passwords,
and watches the support channel for `$nosync` commands from users who
don't want their messages synchronized to YouTube.

```
./monitor_discord_bot.py <discord guild ID> <support channel ID>
```

### Track Viewer Count Bot (`track_viewer_count_bot.py`)

The track viewer count bot tracks the concurrent viewer statistics
for each live Youtube broadcast and periodically posts a chart displaying
the viewer statistics to the session's Discord channel. The bot
is run similar to the chat sync bot, by passing the schedule sheet,
day, and time to run for. The bot will track the live streams active
on the day at the specified time.

```
./track_viewer_count_bot.py <schedule sheet.xlsx> <day> <time>
```

## Additional Utilities

There are additional utilities that might be useful when running a virtual
conference for managing videos or exporting schedule data to JSON (as needed
for a webpage).

### Export JSON (`export_json.py`)

This script exports the schedule data for the conference to JSON for
use in populating a conference webpage. The script can also output
ICS files for each session, event, and the entire conference.

### Upload YouTube Videos (`upload_yt_videos.py`)

This script uploads YouTube videos given the video files, descriptions,
and optional playlist names to create, in an Excel file. The file
should be formatted as shown [here](https://docs.google.com/spreadsheets/d/19JJxdS71Zmhq2cK5NbgmJK_tzrBb2Eb5FJlVXruP4gc/edit?usp=sharing).

### Fix Subtitle Sequencing (`fix_subtitle_sequencing.py`)

When generating subtitles using YouTube and downloading them, the subtitles can
often overlap each other in time, making them hard to follow. This script adjusts
the subtitle timing such that they never overlap, ensuring only one subtitle is shown
on screen at once.

### Assign SV Videos (`assign_sv_videos.py`)

This script can be used to generate review packages for student volunteers to check
the videos for encoding errors. The script also performs automated checks on
file encoding and video length.

### Report Missing Info (`report_missing_info.py`)

This script produces a report of all missing information in the schedule sheet (marked MISSING),
and videos reference by the sheet that aren't found in the specified asset directory.

### Archive Discord (`archive_discord.py`)

This script can be used to archive a Discord server's chat history to a JSON file

### Print Schedule (`print_schedule.py`)

This script can be used to print the schedule as it would be mapped to the
streaming computers. This is useful for validating the conference schedule
can be streamed on the set of computers given the setup and buffer time
required between sessions.

