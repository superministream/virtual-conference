import sys
import os
import http.client
import httplib2
import time
from docopt import docopt
from apiclient.http import MediaFileUpload
from apiclient.errors import HttpError

import core.schedule as schedule
import core.auth as conf_auth
import core.excel_db as excel_db

USAGE = """
Upload the Videos to YouTube

Usage:
    upload_yt_videos.py <video_list.xlsx> <video_root_path> [--no-update]
"""

arguments = docopt(USAGE)

sheet_name = "VIS 2021"
title_field = "Title"
authors_field = "Authors"
description_field = "Abstract/Description"
video_file_field = "Video File"
subtitles_file_field = "Subtitles File"
playlist_prefix_field = "All Playlist Prefix"
playlist_field = "All Playlist Title"

out_youtube_video_field = "Video URL"
out_youtube_playlist_field = "Playlist URL"

infile = arguments["<video_list.xlsx>"]
outfile = os.path.splitext(infile)[0] + "_uploaded.xlsx"

video_db = excel_db.open(infile)
video_table = video_db.get_table(sheet_name)
video_root_path = arguments["<video_root_path>"]
update_descriptions = not arguments["--no-update"]

RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, http.client.NotConnected,
        http.client.IncompleteRead, http.client.ImproperConnectionState,
        http.client.CannotSendRequest, http.client.CannotSendHeader,
        http.client.ResponseNotReady, http.client.BadStatusLine)

def upload_video(video, title, description, auth):
    upload_request = auth.youtube.videos().insert(
        part="id,status,snippet",
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": 27 # Category 27 is "education"
            },
            "status": {
                "privacyStatus": "unlisted",
                "selfDeclaredMadeForKids": False,
                "embeddable": True
            }
        },
        media_body=MediaFileUpload(video, chunksize=-1, resumable=True)
    )

    httplib2.RETRIES = 1
    response = None
    error = None
    retries = 0
    while not response:
        try:
            print(f"Uploading Video:\ntitle = {title}\nauthors = {authors}\nvideo = {video}")
            status, response = upload_request.next_chunk()
            if response:
                if "id" in response:
                    print(f"Uploaded\ntitle = {title}\nauthors = {authors}\nvideo = {video}")
                    return response
                else:
                    print("Upload failed with an unexpected response")
                    return None
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"Retriable HTTP error {e.resp.status}: {e.content}"
            else:
                raise e
        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable exception occured {e}"

        if error:
            print(error)
            retries += 1
            if retries > 10:
                print("Reached max retries, aborting")
                break
            time.sleep(1)

    return None

def update_video(video_id, title, description, auth):
    print("Updating\ntitle = {}\nauthors = {}\nvideo = {}".format(title, authors, video_id))
    upload_response = auth.youtube.videos().update(
        part="id,snippet,status",
        body = {
            "id": video_id,
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": 27 # Category 27 is "education"
            }
        }
    ).execute()
    return upload_response

def get_all_playlists(auth):
    all_playlists = []
    page_token = None
    while True:
        playlists = auth.youtube.playlists().list(
            part="snippet,contentDetails",
            maxResults=50,
            mine=True,
            pageToken=page_token
        ).execute()
        all_playlists += playlists["items"]
        if "nextPageToken" not in playlists:
            break
        page_token = playlists["nextPageToken"]
    return all_playlists

def get_playlist_items(auth, playlist_id):
    all_items = []
    page_token = None
    while True:
        items = auth.youtube.playlistItems().list(
            part="id,snippet,status",
            maxResults=50,
            playlistId=playlist_id,
            pageToken=page_token
        ).execute()
        all_items += items["items"]
        if "nextPageToken" not in items:
            break
        page_token = items["nextPageToken"]
    return all_items

if not out_youtube_video_field in video_table.index or not out_youtube_playlist_field in video_table.index:
    index = [None] * len(video_table.index)
    for k, v in video_table.index.items():
        index[v - 1] = k
    if not out_youtube_video_field in video_table.index:
        index.append(out_youtube_video_field)
    if not out_youtube_playlist_field in video_table.index:
        index.append(out_youtube_playlist_field)
    video_table.set_index(index)

# Validate the input sheet
to_upload = []
total_bytes = 0
all_files_found = True
for r in range(2, video_table.table.max_row + 1):
    video_info = video_table.row(r)
    # If there's no video, or it was already uploaded, skip verifying the file
    # exists because we don't need it
    if not video_info[video_file_field].value or video_info[out_youtube_video_field].value:
        continue
    if video_info[video_file_field].value == "NA":
        continue
    video = os.path.join(video_root_path, video_info[video_file_field].value)
    if not os.path.isfile(video):
        all_files_found = False
        print(f"Video '{video}' was not found")
    else:
        total_bytes += os.path.getsize(video)
        to_upload.append(video)
    subtitles = video_info[subtitles_file_field].value
    if subtitles:
        subtitles = os.path.join(video_root_path, video_info[subtitles_file_field].value)
        if not os.path.isfile(subtitles):
            all_files_found = False
            print("Subtitles {} were not found".format(subtitles))

print(f"Will upload {len(to_upload)} videos")
print(f"Total data upload size: {total_bytes * 1e-6}MB")
for v in to_upload:
    print(v)
if not all_files_found:
    print(f"WARNING: Some files were not found.")
go = input("Proceed with upload? (y/n): ")
if go == "n":
    sys.exit(0)

auth = conf_auth.Authentication(youtube=True, use_pickled_credentials=True)
playlists = {}
print("Getting playlists")
yt_playlists = get_all_playlists(auth)
current_playlists = {}
for pl in yt_playlists:
    title = pl["snippet"]["title"]
    current_playlists[title] = {
        "id": pl["id"],
        "videos": []
    }
    items = get_playlist_items(auth, pl["id"])
    for i in items:
        current_playlists[title]["videos"].append(i["snippet"]["resourceId"]["videoId"])

print("Starting upload")
videos_uploaded = 0
for r in range(2, video_table.table.max_row + 1):
    video_info = video_table.row(r)
    if not video_info[video_file_field].value:
        continue

    if videos_uploaded >= 95:
        print("Stopping after uploading 95 videos, approaching upload limit")
        break

    print(f"{video_info[video_file_field].value}")

    title = schedule.make_youtube_title(video_info[title_field].value)

    description = "Title: " + video_info[title_field].value

    authors = None
    if video_info[authors_field].value:
        authors = video_info[authors_field].value.replace("|", ", ")
    else:
        authors = video_info["Contributor(s)"].value.replace("|", ", ")

    description += "\nAuthors: " + authors
    if video_info[description_field].value:
        description += "\n" + video_info[description_field].value

    # Make sure description text content is valid for Youtube
    description = schedule.make_youtube_description(description)

    # Upload the video
    video_id = None
    if not video_info[out_youtube_video_field].value:
        video = os.path.join(video_root_path, video_info[video_file_field].value)
        if not os.path.isfile(video):
            print(f"Skipping uploading missing file {video}")
            print("----")
            continue

        videos_uploaded += 1
        try:
            upload_response = upload_video(video, title, description, auth)
            print(upload_response)
            video_info[out_youtube_video_field].value = "https://youtu.be/" + upload_response["id"]
            video_id = upload_response["id"]
        except Exception as e:
            print("Failed to upload {}: {}".format(video, e))
            print("Stopping uploading")
            break

        subtitles = video_info[subtitles_file_field].value
        # Upload the subtitles
        if subtitles:
            try:
                subtitles = os.path.join(video_root_path, video_info[subtitles_file_field].value)
                subtitles_response = auth.youtube.captions().insert(
                    part="id,snippet",
                    body={
                        "snippet": {
                            "videoId": upload_response["id"],
                            "language": "en-us",
                            "name": video_info[subtitles_file_field].value
                        }
                    },
                    media_body=MediaFileUpload(subtitles)
                ).execute()
                print(subtitles_response)
            except Exception as e:
                print("Failed to upload {}: {}".format(subtitles, e))
    else:
        video_id = schedule.match_youtube_id(video_info[out_youtube_video_field].value)
        if update_descriptions:
            update_response = update_video(video_id, title, description, auth)
            print(update_response)

    if video_id:
        if video_info[playlist_field].value and not video_info[out_youtube_playlist_field].value:
            playlist_title = video_info[playlist_prefix_field].value + " - " + str(video_info[playlist_field].value)
            if playlist_title[0:4] == "VIS ":
                playlist_title = "VIS21" + playlist_title[3:]

            playlist_title = schedule.make_youtube_title(playlist_title)
            if not playlist_title in playlists:
                playlists[playlist_title] = []
            if not video_id in playlists[playlist_title]:
                playlists[playlist_title].append(video_id)
            else:
                print("Video already in playlist")
    else:
        print("Video {} was not uploaded".format(title))
    video_db.save(outfile)
    print("----")

video_db.save(outfile)
# Create new playlists we need and add videos to the playlists
print(playlists)
for pl, videos in playlists.items():
    # Create new playlists if needed
    if pl not in current_playlists:
        resp = auth.youtube.playlists().insert(
            part="id,status,snippet",
            body={
                "snippet": {
                    "title": pl
                },
                "status": {
                    "privacyStatus": "unlisted"
                }
            }).execute()
        current_playlists[pl] = {
            "id": resp["id"],
            "videos": []
        }
    
    for v in videos:
        if v not in current_playlists[pl]["videos"]:
            resp = auth.youtube.playlistItems().insert(
                part="id,status,snippet",
                body={
                    "snippet": {
                        "playlistId": current_playlists[pl]["id"],
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": v
                        }
                    }
                }).execute()

        r = video_table.find(out_youtube_video_field, "https://youtu.be/" + v)
        video_table.entry(r[0], out_youtube_playlist_field).value = "https://www.youtube.com/playlist?list={}".format(current_playlists[pl]["id"])
        video_db.save(outfile)

video_db.save(outfile)

