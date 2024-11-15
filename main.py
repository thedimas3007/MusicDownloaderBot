from youtubesearchpython.__future__ import VideosSearch

import re
import requests
from requests import HTTPError

from rich.pretty import pprint
from rich import inspect

from aiogram import Bot, Dispatcher, executor, types
from yaml import load, dump, Loader

from odesli.Odesli import Odesli
from yt_dlp import YoutubeDL
from spotipy import Spotify, SpotifyClientCredentials

from os import mkdir, remove, walk
from os.path import exists

from logger import Logger

# TODO:
# - Add support for playlists/albums for Spotify and Youtube
#   - Ability to stop downloading
# - Multiple pages in search results
# - Add metadata to MP3 files
# - Spotify search
# - "Cache" channel with songs


url_regex = r"^(https?:\/\/)?([\da-z\.-]+\.[a-z\.]{2,6})(.*)\/?#?$"
youtube_domains = ("m.youtube.com", "youtube.com", "www.youtube.com", "youtu.be", "music.youtube.com")
spotify_domains = ("open.spotify.com",)
spotify_regex = {
    "track": r"(?:https:\/\/open\.spotify\.com\/playlist\/|spotify:playlist:)([a-zA-Z0-9]+)",
    "album": r"(?:https:\/\/open\.spotify\.com\/album\/|spotify:album:)([a-zA-Z0-9]+)"
}

log = Logger()
config = load(open("config.yml"), Loader=Loader)
bot = Bot(config["bot_token"])
dp = Dispatcher(bot)
odesli = Odesli()
ytdl = YoutubeDL({
    "format": "bestaudio/best",
    "outtmpl": "cache/%(id)s.%(ext)s",
    "cookies": "cookies.txt",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "320",
    }],
})
spotify = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=config["spotify_id"],
    client_secret=config["spotify_secret"]
))

if not exists("cache"):
    mkdir("cache")
else:
    if w := walk("cache"):
        log.info("Clearing cache...")
        for f in w:
            for file in f[2]:
                log.info(f"Removing [yellow]{f[0]}/{file}[/]")
                remove(f[0] + "/" + file)


def save_url(url: str, path: str):
    r = requests.get(url)
    with open(path, "wb") as out:
        out.write(r.content)
    return path


async def handle_song(message: types.Message, song, meta, song_link: str):
    log.info(f"Downloading [blue]{song.id}[/]")
    await message.edit_text("⏳ Downloading...")
    ytdl.download(list(song.linksByPlatform.values())[:1])

    log.info(f"Saving thumbnail for [blue]{song.id}[/]")
    thumb = save_url(meta.thumbnailUrl, f"cache/{song.id}.jpg")

    log.info(f"Sending [blue]{song.id}[/]")
    await message.edit_text("⏳ Uploading...")
    await message.answer_audio(types.InputFile(f"cache/{song.id}.mp3"),
                               caption=f"_[song\\.link]({song_link})_",
                               parse_mode="MarkdownV2",
                               performer=meta.artistName,
                               title=meta.title,
                               thumb=open(thumb, "rb"))
    await message.delete()
    remove(thumb)
    remove(f"cache/{song.id}.mp3")


async def handle_youtube(message: types.Message, url: str):
    new = await message.answer("⏳ Acquiring metadata...")
    result = odesli.getByUrl(url)
    yt = result.songsByProvider["youtube"]
    meta = result.songsByProvider["youtube"]
    if "spotify" in result.songsByProvider.keys():
        meta = result.songsByProvider["spotify"]
    else:
        log.warn(f"No Spotify link found for {url}")

    await handle_song(new, yt, meta, result.songLink)


@dp.message_handler(regexp=url_regex)
async def handle_url(message: types.Message):
    # TODO: Add support for playlists (so far only Spotify and Youtube)
    new = await message.reply("⏳ Acquiring metadata...")
    try:
        log.info(f"Got URL: [blue]{message.text}[/] from [blue]{message.from_user.full_name}[/] / [blue]{message.from_id}[/]")
        result = odesli.getByUrl(message.text)
        if "youtube" not in result.songsByProvider.keys():
            log.warn(f"No YouTube link found for [yellow]{message.text}[/]")
            await message.reply("⚠ Song not found!")
            return
        yt = result.songsByProvider["youtube"]
        meta = result.songsByProvider["youtube"]
        if "spotify" in result.songsByProvider.keys():
            meta = result.songsByProvider["spotify"]
        else:
            log.warn(f"No Spotify link found for [yellow]{message.text}[/]")
        await handle_song(new, yt, meta, result.songLink)
    except HTTPError as e:
        if e.response.status_code >= 400 and e.response.status_code < 500:
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


@dp.message_handler()
async def handle_text(message: types.Message):
    log.info(f"Got text: [blue]{message.text}[/] from [blue]{message.from_user.full_name}[/] / [blue]{message.from_id}[/]")
    log.info(f"Searching [blue]{message.text}[/]")
    new = await message.reply("⏳ Searching...")

    search = VideosSearch(message.text, limit=config["search_limit"])
    results = (await search.next())["result"]
    log.info(f"Got {len(results)} results")
    if len(results) == 0:
        await new.edit_text("🔎 No results found")
        return

    buttons = []
    for vid in results:
        buttons.append([
            types.InlineKeyboardButton(text=f"{vid['title']} - {vid['channel']['name']}", callback_data=vid["link"])
        ])
    await new.edit_text("🔎 Search results", reply_markup=types.InlineKeyboardMarkup(row_width=1, inline_keyboard=buttons))


@dp.callback_query_handler()
async def handle_callback(query: types.CallbackQuery):
    log.info(f"Got callback: [blue]{query.data}[/] from [blue]{query.from_user.full_name}[/] / [blue]{query.from_user.id}[/]")
    await query.answer()
    await handle_youtube(query.message, query.data)


if __name__ == "__main__":
    log.info("Starting polling...")
    executor.start_polling(dp, skip_updates=True)
