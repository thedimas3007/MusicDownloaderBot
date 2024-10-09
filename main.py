import re
import requests
import rich
from requests import HTTPError

from rich.pretty import pprint
from rich import inspect

from aiogram import Bot, Dispatcher, executor, types
from yaml import load, dump, Loader

from odesli.Odesli import Odesli
from yt_dlp import YoutubeDL
from youtubesearchpython import VideosSearch
from spotipy import Spotify, SpotifyClientCredentials

from os import mkdir, remove
from os.path import exists

from logger import Logger

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
    "outtmpl": "cache/%(id)s.%(ext)s",
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '320',
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
    return path


async def handle_song(message: types.Message, song, meta, song_link: str):
    log.info(f"Downloading {song.id}")
    await message.edit_text("⏳ Downloading...")
    ytdl.download(list(song.linksByPlatform.values())[:1])

    log.info(f"Saving thumbnail for {song.id}")
    thumb = save_url(meta.thumbnailUrl, f"cache/{song.id}.jpg")

    log.info(f"Sending {song.id}")
    await message.edit_text("⏳ Sending...")
    await message.answer_audio(types.InputFile(f"cache/{song.id}.mp3"),
                               caption=f"__[song\\.link]({song_link})__",
                               parse_mode="MarkdownV2",
                               performer=meta.artistName,
                               title=meta.title,
                               thumb=open(thumb, "rb"))
    await message.delete()
    remove(thumb)
    remove(f"cache/{song.id}.mp3")


@dp.message_handler(regexp=url_regex)
async def handle_url(message: types.Message):
    # TODO: Add support for playlists (so far only Spotify)
    new = await message.reply("⏳ Acquiring metadata...")
    try:
        log.info(f"Got URL: {message.text} from {message.from_user.full_name} / {message.from_id}")
        result = odesli.getByUrl(message.text)
        if "youtube" not in result.songsByProvider.keys():
            log.warn(f"No YouTube link found for {message.text}")
            await message.reply("⚠ Song not found!")
            return
        yt = result.songsByProvider["youtube"]
        meta = result.songsByProvider["youtube"]
        if "spotify" in result.songsByProvider.keys():
            meta = result.songsByProvider["spotify"]
        else:
            log.warn(f"No Spotify link found for {message.text}")

        await handle_song(new, yt, meta, result.songLink)
    except HTTPError as e:
        if e.response.status_code >= 400 and e.response.status_code < 500:
            # TODO: Use YouTube as a fallback for YT links, e.g. podcasts
            log.warn(f"Code {e.response.status_code} for {message.text}")
            await new.edit_text("⚠ Song not found!")
            return
        else:
            log.console.print_exception()
            await new.edit_text("⚠ Unknown HTTP error occurred!")
    except Exception:
        log.console.print_exception()
        await new.edit_text("⚠ Unknown error occurred!")
        return


if __name__ == "__main__":
    log.info("Starting polling...")
    executor.start_polling(dp, skip_updates=True)
