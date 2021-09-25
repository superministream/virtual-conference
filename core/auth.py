import json
import os
import sys
import boto3
import pickle
import requests
import eventbrite
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

from urllib.parse import urlsplit
from google.auth.transport.requests import Request

# The SUPERMINISTREAM_AUTH_FILE file should be a JSON file with the authentication
# information for the APIs to be used. For Zoom, the JWT token should be for the
# admin account, so that it can schedule meetings for the technician accounts.
# For example:
# {
#    "aws": {
#        "access_key": "",
#        "secret_key": "",
#        "region": ""
#    },
#    "discord": {...},
#    "google": {
#        "installed": {...}
#    },
#    "zoom": {
#        "jwt_token": {...}
#    },
#    "eventbrite": ""
#    "eventbrite_event_id": <number>
#    "auth0": {
#        "client_id": "",
#        "client_secret": "",
#        "audience": "",
#        "connection_id": ""
# }
class Authentication:
    def __init__(self, youtube=False, email=False, use_pickled_credentials=False,
            eventbrite_api=False,
            auth0_api=False):
        # Setup API clients
        if not "SUPERMINISTREAM_AUTH_FILE" in os.environ:
            print("You must set $SUPERMINISTREAM_AUTH_FILE to the json file containing your authentication credentials")
            sys.exit(1)

        if youtube and not "YOUTUBE_AUTH_PICKLE_FILE" in os.environ:
            print("You must set $YOUTUBE_AUTH_PICKLE_FILE to the Youtube pickled auth file")
            sys.exit(1)

        auth_file = os.environ["SUPERMINISTREAM_AUTH_FILE"]
        with open(auth_file, "r") as f:
            auth = json.load(f)
            self.discord = auth["discord"]

            self.zoom = {
                "authorization": "Bearer {}".format(auth["zoom"]["jwt_token"]),
                "content-type": "application/json"
            }

            self.email = None
            self.youtube = None

            if email:
                self.email = boto3.client("ses",
                        aws_access_key_id=auth["aws"]["access_key"],
                        aws_secret_access_key=auth["aws"]["secret_key"],
                        region_name=auth["aws"]["region"])

            if youtube:
                self.youtube = self.authenticate_youtube(auth, use_pickled_credentials)

            if eventbrite_api:
                self.eventbrite = eventbrite.Eventbrite(auth["eventbrite"])
                self.eventbrite_event_id = auth["eventbrite_event_id"]

            if auth0_api:
                self.auth0 = auth["auth0"]

    def authenticate_youtube(self, auth, use_pickled_credentials):
        yt_scopes = ["https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/youtube.force-ssl"]

        pickle_file = os.environ["YOUTUBE_AUTH_PICKLE_FILE"]
        credentials = None
        if use_pickled_credentials and os.path.exists(pickle_file):
            with open(pickle_file, "rb") as f:
                credentials = pickle.load(f)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                # Get credentials and create an API client
                credentials = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
                    auth["google"], yt_scopes).run_local_server()
            # Save the credentials
            if use_pickled_credentials:
                with open(pickle_file, "wb") as f:
                    pickle.dump(credentials, f)

        return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

    def get_auth0_token(self):
        auth0_payload = {
            "client_id": self.auth0["client_id"],
            "client_secret": self.auth0["client_secret"],
            "audience": self.auth0["audience"],
            "grant_type": "client_credentials"
        }
        domain = "https://" + urlsplit(self.auth0["audience"]).netloc
        resp = requests.post(domain + "/oauth/token", json=auth0_payload).json()
        return resp["access_token"]


