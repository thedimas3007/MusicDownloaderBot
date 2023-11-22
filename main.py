import re
import requests

from aiogram import Bot, Dispatcher, executor, types
from asyncio import get_event_loop
from yaml import load, dump, Loader
from pytube import Search, YouTube, Channel

from os import mkdir, remove
from os.path import exists

from logger import Logger

URL_REGEX = r"^(https?:\/\/)?([\da-z\.-]+\.[a-z\.]{2,6})([\/\w \.-]*)\/?#?$"

log = Logger()
config = load(open("config.yml"), Loader=Loader)
bot = Bot(config["bot_token"])
dp = Dispatcher(bot)

if not exists("cache"):
    mkdir("cache")

def save_url(url: str, path: str):
    r = requests.get(url)
    with open(path, "wb") as out:
        out.write(r.content)


@dp.message_handler(regexp=URL_REGEX)
async def on_url(message: types.Message):
    match = re.match(URL_REGEX, message.text)
    await message.answer(text=f"Site: {match[2]}\nPayload: {match[3]}")

@dp.message_handler()
async def on_message(message: types.Message):
    log.info(f"Searching for {message.text} from {message.from_user.full_name} ({message.from_id})...")
    search = Search(message.text)
    results = search.results
    log.success(f"Found {len(results)} results")

    yt = results[0]
    yt: YouTube
    channel = Channel(yt.channel_url)
    yt.use_oauth=True
    yt.allow_oauth_cache=True

    filename = f"cache/dl_{yt.video_id}.mp3"
    thumb = f"cache/thumb_{yt.video_id}.jpg"

    log.info(f"Downloading {yt.watch_url} into {filename}...")
    msg = await message.answer(f"⏳ Downloading <a href='{yt.watch_url}'>{yt.title}</a>...", parse_mode="html", disable_web_page_preview=True)
    yt.streams.filter(only_audio=True).first().download(filename=filename)
    save_url(yt.thumbnail_url, thumb)
    log.success("Succesfully donwloaded")
    log.info("Uploading...")
    await message.answer_audio(audio=open(filename, "rb"), 
                               title=yt.title,
                               performer=channel.channel_name, 
                               duration=yt.length,
                               thumb=open(thumb, "rb"),
                               caption=f"<a href='{yt.watch_url}'>{yt.title}</a>",
                               parse_mode="html")
    await msg.delete()
    log.success("Successfully uploaded")
    remove(filename)
    remove(thumb)


if __name__ == "__main__":
    log.info("Starting polling...")
    executor.start_polling(dp, skip_updates=True)