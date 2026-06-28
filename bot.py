import os
import re
import asyncio
import logging
import tempfile
import shutil
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DOWNLOAD_DIR = tempfile.gettempdir()
INSTAGRAM_PATTERN = re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories|share/reel)/[\w\-/?=&%]+")

def extract_url(text):
    m = INSTAGRAM_PATTERN.search(text)
    return m.group(0) if m else None

def ydl_opts(out):
    return {
        "outtmpl": out,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
        "http_headers": {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"},
        "retries": 5,
    }

async def download(url):
    d = tempfile.mkdtemp(dir=DOWNLOAD_DIR)
    tpl = os.path.join(d, "%(id)s.%(ext)s")
    try:
        loop = asyncio.get_event_loop()
        def run():
            with yt_dlp.YoutubeDL(ydl_opts(tpl)) as ydl:
                info = ydl.extract_info(url, download=True)
                f = ydl.prepare_filename(info)
                if not f.endswith(".mp4"):
                    f = os.path.splitext(f)[0] + ".mp4"
                return f
        fp = await loop.run_in_executor(None, run)
        dest = tempfile.mktemp(suffix=".mp4")
        shutil.move(fp, dest)
        shutil.rmtree(d, ignore_errors=True)
        return dest, None
    except yt_dlp.utils.DownloadError as e:
        shutil.rmtree(d, ignore_errors=True)
        msg = str(e).lower()
        if "login" in msg or "private" in msg:
            return None, "🔒 Bu post yopiq (private)."
        if "404" in msg or "not found" in msg:
            return None, "❌ Video topilmadi yoki o'chirilgan."
        return None, "⚠️ Yuklash muvaffaqiyatsiz. Havolani tekshiring."
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        return None, "⚠️ Xatolik yuz berdi. Qayta urinib ko'ring."

async def start(update, context):
    await update.message.reply_text("👋 Salom! Instagram reel/post havolasini yuboring — yuklab beraman!\n\nMisol: https://www.instagram.com/reel/ABC123/")

async def handle(update, context):
    text = (update.message.text or "").strip()
    url = extract_url(text)
    if not url:
        await update.message.reply_text("🔗 To'g'ri Instagram havolasini yuboring.")
        return
    msg = await update.message.reply_text("⏬ Yuklanmoqda...")
    fp, err = await download(url)
    if err:
        await msg.edit_text(err)
        return
    size_mb = os.path.getsize(fp) / 1024 / 1024
    await msg.edit_text(f"📤 Jo'natilmoqda... ({size_mb:.1f} MB)")
    try:
        with open(fp, "rb") as f:
            await update.message.reply_video(video=f, caption="✅ Instagram yuklovchi bot", supports_streaming=True, read_timeout=300, write_timeout=300)
        await msg.delete()
    except Exception as e:
        await msg.edit_text("⚠️ Jo'natishda xatolik. Video juda katta bo'lishi mumkin.")
    finally:
        if os.path.exists(fp):
            os.remove(fp)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    logger.info("Bot ishga tushdi ✅")
    app.run_polling()

if __name__ == "__main__":
    main()
