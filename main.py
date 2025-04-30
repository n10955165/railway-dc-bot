import discord
from discord.ext import commands
from discord.commands import Option
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import google.generativeai as genai
import yt_dlp
import traceback
from bs4 import BeautifulSoup
import requests
import asyncio
import random
import aiohttp


# ====== Keep Alive（Replit専用） ======
app = Flask('')

@app.route('/')
def home():
    return "online"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# ====== 認証情報読み込み ======
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ====== Gemini API 初期化 ======
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash-latest")

# ====== Discord Bot 初期化 ======
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
last_song_title = None

# ====== YouTube再生機能 ======
async def play_youtube(query, text_channel):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'default_search': 'ytsearch1',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)

            if 'entries' in info:
                info = info['entries'][0]

            title = info.get("title", "Unknown Title")
            url = info.get("webpage_url", "URLが見つからなかった…")

        await text_channel.send(f"🎵 推薦曲名：**{title}**\n📺 {url}")

    except Exception:
        await text_channel.send(f"⚠️ 曲を探す時に問題があったよ：\n```{traceback.format_exc()}```")



# ====== イベント ======
@bot.event
async def on_ready():
    print(f"✅ 起動完了！ログイン中: {bot.user}")

# ====== スラッシュコマンド：兄控チャット ======
@bot.slash_command(name="onichan", description="妹ちゃんとお話しよっ")
async def onichan(ctx, メッセージ: Option(str, "お兄ちゃん、何を言いたいの？")):
    await ctx.respond("...")

    try:
        prompt = f"""
あなたは今、兄が大好きでたまらない「兄控えめな妹」です。
話し方は甘くて、ちょっと依存気味で、恥ずかしがりながらもお兄ちゃんに甘える感じにしてください。
返答は必ず日本語で書いてください。

ユーザー（お兄ちゃん）が言った：
{メッセージ}
        """
        response = model.generate_content(prompt)
        await ctx.send(response.text)

    except Exception as e:
        await ctx.send(f"💔 えええっ…なんかエラー出ちゃった…：{e}")

# ====== スラッシュコマンド：Vocaloid曲再生 ======
# ====== 歷史記憶（全域變數）======
recent_songs = []

@bot.slash_command(name="play", description="妹ちゃんがVocaloid曲を選んでくれるよ🎵")
async def play(ctx):
    global recent_songs

    await ctx.respond("うふふ…お兄ちゃんにぴったりな曲を探してくるね…💗")

    # 整理最近推薦過的曲名列表（如果沒推薦過就空白）
    history_text = "、".join(recent_songs) if recent_songs else "なし"

    prompt = f"""
あなたは兄が大好きな妹キャラです。日本語で答えてください。
今おすすめしたいVocaloid曲を一つだけ選んでください。

条件：
- 過去に推薦した曲（{history_text}）と同じ曲、または超有名な曲（例：千本桜、メルトなど）は選ばないでください。
- あまり知られていない、でも素敵なVocaloid曲を選んでください。
- 形式は必ず『推薦曲名：<曲名>』だけ。他の言葉や説明は禁止です。

注意：
- 有名すぎる曲は禁止です。
- 同じ曲は絶対に選ばないでください。
    """

    try:
        ai_response = model.generate_content(prompt)
        text = ai_response.text.strip()

        if "推薦曲名：" in text:
            song_title = text.split("推薦曲名：")[1].strip()
            if not song_title:
                await ctx.send("えへへ…曲の名前、ちょっと忘れちゃったかも…？もう一度お願い〜💦")
                return

            # 如果曲子還是重複，直接告知
            if song_title in recent_songs:
                await ctx.send("うぅ…また同じ曲になっちゃいそう…もう一回試してみるね💦")
                return

            # 記住這首歌
            recent_songs.append(song_title)
            if len(recent_songs) > 10:
                recent_songs.pop(0)  # 保持只記錄10首

            await play_youtube(song_title, ctx.channel)

        else:
            await ctx.send("えへへ…曲の名前、ちょっと忘れちゃったかも…？もう一度お願い〜💦")

    except Exception as e:
        await ctx.send(f"💔 お兄ちゃん、ごめんね…：{e}")

# ====== anime推薦功能 (用Jikan直接顯示) ======

anime_history = set()

async def search_jikan_anime(keyword):
    async with aiohttp.ClientSession() as session:
        params = {"q": keyword, "limit": 1}
        async with session.get("https://api.jikan.moe/v4/anime", params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("data"):
                    anime = data["data"][0]
                    return anime
    return None

async def generate_anime_title():
    prompt = (
        "あなたは兄が大好きな妹キャラです。\n"
        "今おすすめしたい、まだあまり知られていない隠れた名作アニメを、繁體字で1作品だけ教えてください。\n"
        "必須條件：2010年以後放送、現象級作品以外（例如鬼滅、進擊、咒術、SpyFamily之類都禁止）\n"
        "格式：『推薦作品名：<作品名>』。其他說明不要。"
    )
    ai_response = model.generate_content(prompt)
    text = ai_response.text
    if "推薦作品名：" in text:
        anime_title = text.split("推薦作品名：")[1].strip()
        return anime_title
    else:
        return None

@bot.slash_command(name="anime", description="妹ちゃんがアニメをオススメしてくれるよ🎬")
async def anime(ctx):
    await ctx.respond("うふふ…お兄ちゃんにぴったりな隠れた名作を探してくるねっ💗")

    max_retry = 5

    for _ in range(max_retry):
        anime_title = await generate_anime_title()

        if not anime_title:
            continue

        if anime_title in anime_history:
            continue

        anime_info = await search_jikan_anime(anime_title)

        if anime_info:
            year = anime_info.get("year", 0)
            members = anime_info.get("members", 0)

            if year and year >= 2010 and members and members < 500000:  # 2010後 + 不是超人氣
                anime_history.add(anime_title)

                title = anime_info.get("title")
                url = anime_info.get("url")
                synopsis = anime_info.get("synopsis", "（沒有簡介）")

                await ctx.send(f"🎬 推薦作品名：**{title}**\n🔗 {url}\n📝 簡介：{synopsis}")
                return

        await asyncio.sleep(1)

    await ctx.send("😭 ごめんね…一生懸命探したけど、ぴったりな作品が見つからなかったよ…💦")



# ====== 天氣查詢指令（改良版） ======
@bot.slash_command(name="weather", description="妹ちゃんがお天気教えてあげるっ☀️")
async def weather(ctx, city: Option(str, "どこの天気を知りたい？（都市名を入力してね）")):
    await ctx.respond("ちょっと待っててね…お兄ちゃん…💖")

    weather_api_key = os.getenv("WEATHER_API_KEY")
    url = f"http://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={city}&lang=ja"

    try:
        response = requests.get(url)
        data = response.json()

        if "error" in data:
            await ctx.send(f"ううぅ…その場所、見つからなかったみたい💦\n（エラー：{data['error']['message']}）")
            return

        # 拿資料
        temp_c = data['current']['temp_c']
        condition = data['current']['condition']['text']
        humidity = data['current']['humidity']


        # 發送訊息
        message = (
            f"お兄ちゃん、今の **{city}** のお天気だよ〜☀️\n"
            f"🌡️ 気温：**{temp_c}°C**\n"
            f"☁️ 状態：**{condition}**\n"
            f"💧 湿度：**{humidity}%**\n\n"
        )

        await ctx.send(message)

    except Exception as e:
        await ctx.send(f"💔 ごめんね、お兄ちゃん…天気調べてる時にエラーが出ちゃった：{e}")

# ====== スラッシュコマンド：じゃんけん（猜拳） ======
@bot.slash_command(name="rps", description="妹ちゃんとじゃんけんしよっ✊✌️🖐️")
async def rps(ctx, 手: Option(str, "お兄ちゃんの手を選んでね", choices=["グー", "チョキ", "パー"])):
    await ctx.respond("うふふ…お兄ちゃんの考え、読んじゃうからね〜💖")

    try:
        # AIに予測させる
        prompt = f"""
あなたは兄の行動を予測する妹です。
今、お兄ちゃんはじゃんけん（グー＝石、チョキ＝剪刀、パー＝布）をしようとしています。
お兄ちゃんは「{手}」を出すと言っていますが、本心で何を出すか、予測してください。

そのあと、勝てる手を選んでください。
出力は「選んだ手：〜〜」だけ、ほかの説明は不要。
「グー」「チョキ」「パー」で答えてください。
        """
        ai_response = model.generate_content(prompt)
        ai_choice_raw = ai_response.text.strip()

        if "選んだ手：" in ai_choice_raw:
            ai_hand = ai_choice_raw.split("選んだ手：")[1].strip()
        else:
            # 失敗時、ランダム
            import random
            ai_hand = random.choice(["グー", "チョキ", "パー"])

        # 判定ロジック
        result = ""
        if ai_hand == 手:
            result = "あいこだねっ💖（平手）"
        elif (手 == "グー" and ai_hand == "パー") or (手 == "チョキ" and ai_hand == "グー") or (手 == "パー" and ai_hand == "チョキ"):
            result = "お兄ちゃん、負けちゃったねっ💖"
        else:
            result = "お兄ちゃん、勝ったねっ✨"

        await ctx.send(f"✊✌️🖐️\nお兄ちゃんは【{手}】、妹ちゃんは【{ai_hand}】を出したよ！\n\n{result}")

    except Exception as e:
        await ctx.send(f"💔 ごめんね…考えてる途中でエラー出ちゃった…：{e}")

# ====== 普通のメッセージ反応（旧式） ======
@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.author == bot.user:
        return
    if message.content.startswith("!hello"):
        await message.channel.send("やっほ〜お兄ちゃんっ💖")

# ====== Bot起動 ======
bot.run(TOKEN)

