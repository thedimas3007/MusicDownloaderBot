import re
import requests

from aiogram import Bot, Dispatcher, executor, types
from asyncio import get_event_loop
from yaml import load, dump, Loader

from pytube import Search, YouTube, Channel
from pytube.exceptions import AgeRestrictedError

from os import mkdir, remove
from os.path import exists

from logger import Logger

URL_REGEX = r"^(https?:\/\/)?([\da-z\.-]+\.[a-z\.]{2,6})([\/\w \.-]*)\/?#?$"
SUPPORTED_SITES = ["m.youtube.com", "youtube.com", "www.youtube.com", "youtu.be"]  # so far only YT

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

async def send_yt(message: types.Message, yt: YouTube):
    msg = await message.answer(f"⏳ Downloading <a href='{yt.watch_url}'>{yt.title}</a>...", parse_mode="html", disable_web_page_preview=True)
    try:    
        channel = Channel(yt.channel_url)
        yt.use_oauth=True
        yt.allow_oauth_cache=True

        filename = f"cache/dl_{yt.video_id}.mp3"
        thumb = f"cache/thumb_{yt.video_id}.jpg"

        log.info(f"Downloading {yt.watch_url} into {filename}...")
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
        log.success("Successfully uploaded")
    except AgeRestrictedError:
        await message.reply("⚠️ The video is age restricted")
    except Exception as e:
        await message.reply("⚠️ Unknown exception occurred")
        log.error(f"Unknown error occurred, caused by {message.from_user.full_name} ({message.from_id})")
        log.error(e.with_traceback())
    
    await msg.delete()
    if exists(filename): remove(filename)
    if exists(thumb): remove(thumb) 


@dp.message_handler()
async def on_message(message: types.Message):
    if match := re.match(URL_REGEX, message.text):
        if match[2] not in SUPPORTED_SITES:
            log.warn(f"Unsuppored site {match[2]} asked by {message.from_user.full_name} ({message.from_id})")
            await message.reply(f"⚠️ Unfortunately, {match[2]} is not currently supported")
            return
        else:
            log.info(f"Downloading {message.text} {message.from_user.full_name} ({message.from_id})...")
            send_yt(message, YouTube(message.text))
    else:
        log.info(f"Searching for {message.text} from {message.from_user.full_name} ({message.from_id})...")
        search = Search(message.text)
        results = search.results
        log.success(f"Found {len(results)} results")
        if (len(results) == 0):
            await message.reply("⚠️ Nothing found")
        else:
            # await send_yt(message, results[0])
            results = results[:10]
            buttons = []
            for yt in results:
                yt: YouTube
                buttons.append([
                    types.InlineKeyboardButton(text=yt.title, callback_data=yt.watch_url)
                ])
            await message.answer("🔎 Search results",
                           reply_markup=types.InlineKeyboardMarkup(row_width=1, inline_keyboard=buttons))

@dp.callback_query_handler()
async def on_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    yt = YouTube(callback.data)
    msg = await bot.send_message(chat_id=user_id, text=f"⏳ Downloading <a href='{yt.watch_url}'>{yt.title}</a>...", parse_mode="html", disable_web_page_preview=True)

    try:    
        channel = Channel(yt.channel_url)
        yt.use_oauth=True
        yt.allow_oauth_cache=True

        filename = f"cache/dl_{yt.video_id}.mp3"
        thumb = f"cache/thumb_{yt.video_id}.jpg"

        log.info(f"Downloading {yt.watch_url} into {filename}...")
        yt.streams.filter(only_audio=True).first().download(filename=filename)
        save_url(yt.thumbnail_url, thumb)
        log.success("Succesfully donwloaded")
        log.info("Uploading...")
        await bot.send_audio(chat_id=user_id,
                             audio=open(filename, "rb"), 
                             title=yt.title,
                             performer=channel.channel_name, 
                             duration=yt.length,
                             thumb=open(thumb, "rb"),
                             caption=f"<a href='{yt.watch_url}'>{yt.title}</a>",
                             parse_mode="html")
        log.success("Successfully uploaded")
    except AgeRestrictedError:
        await callback.answer("⚠️ The video is age restricted")
    except Exception as e:
        await callback.answer("⚠️ Unknown exception occurred")
        log.error(f"Unknown error occurred, caused by {callback.from_user.full_name} ({user_id})")
        log.error(e.with_traceback())
    
    await msg.delete()
    if exists(filename): remove(filename)
    if exists(thumb): remove(thumb) 

if __name__ == "__main__":
    log.info("Starting polling...")
    executor.start_polling(dp, skip_updates=True)