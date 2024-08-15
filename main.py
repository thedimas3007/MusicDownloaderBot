import re
import requests
import rich

from aiogram import Bot, Dispatcher, executor, types
from asyncio import get_event_loop

from rich.pretty import pprint
from yaml import load, dump, Loader

from odesli.Odesli import Odesli
from youtube_dl import YoutubeDL
from youtubesearchpython import VideosSearch
from pytube import Search, YouTube, Channel
from pytube.exceptions import AgeRestrictedError
from spotipy import Spotify, SpotifyClientCredentials

from os import mkdir, remove
from os.path import exists

from logger import Logger

# == TODO ==
# - song.link search and message
# - Spotify albums support


url_regex = r"^(https?:\/\/)?([\da-z\.-]+\.[a-z\.]{2,6})(.*)\/?#?$"
youtube_domains = ("m.youtube.com", "youtube.com", "www.youtube.com", "youtu.be", "music.youtube.com")
spotify_domains = ("open.spotify.com",)
spotify_regex = {
    "track": r"(?:https:\/\/open\.spotify\.com\/playlist\/|spotify:playlist:)([a-zA-Z0-9]+)",
    "album": r"(?:https:\/\/open\.spotify\.com\/album\/|spotify:album:)([a-zA-Z0-9]+)"
}
track_limit = 25

log = Logger()
config = load(open("config.yml"), Loader=Loader)
bot = Bot(config["bot_token"])
dp = Dispatcher(bot)
odesli = Odesli()
ytdl = YoutubeDL({
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
})
spotify = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=config["spotify_id"],
    client_secret=config["spotify_secret"]
))

if not exists("cache"):
    mkdir("cache")


def save_url(url: str, path: str):
    r = requests.get(url)
    with open(path, "wb") as out:
        out.write(r.content)


if __name__ == "__main__":
    log.info("Starting polling...")
    executor.start_polling(dp, skip_updates=True)