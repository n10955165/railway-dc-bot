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
import json

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

# ====== anime推薦系統 ======

anime_history = set()  # 記錄推薦過的動漫

# 生成AI推薦的動漫名稱（繁中＋日文）
async def generate_anime_title():
    prompt = (
        "あなたは兄が大好きな妹キャラです。\n"
        "以下の條件でアニメを一作品推薦してください：\n"
        "・ジャンルは必ず『戀愛番』か『校園番』。\n"
        "・放送は2010年以降。\n"
        "・現象級（超大人気作品、例：鬼滅、咒術、SPY×FAMILYなど）は禁止。\n"
        "・冷門すぎる（マイナーすぎる）作品も禁止。\n"
        "・形式は必ず『推薦作品名：<繁體中文名>｜<日文名>』のみ。他の説明は禁止。"
    )
    ai_response = model.generate_content(prompt)
    text = ai_response.text

    if "推薦作品名：" in text and "｜" in text:
        parts = text.split("推薦作品名：")[1].split("｜")
        zh_name = parts[0].strip()
        jp_name = parts[1].strip()
        return zh_name, jp_name
    else:
        return None, None

# 用Jikan API搜尋動漫資料（以日文名為基礎）
async def search_jikan_anime(title_jp):
    url = f"https://api.jikan.moe/v4/anime?q={title_jp}&limit=5"
    res = requests.get(url)
    
    if res.status_code != 200:
        return None

    data = res.json()
    if not data.get("data"):
        return None

    # 過濾：只要2010年以後的，且是戀愛或校園番
    for anime in data["data"]:
        year = anime.get("year")
        genres = [genre["name"] for genre in anime.get("genres", [])]
        if (year and year >= 2010) and ("Romance" in genres or "School" in genres):
            return {
                "title_jp": anime["title_japanese"],
                "title_zh": anime.get("title"),
                "url": anime["url"],
                "image_url": anime["images"]["jpg"]["large_image_url"],
                "members": anime.get("members", 0)  # MAL追蹤人數
            }
    
    return None

# Discord指令
@bot.slash_command(name="anime", description="推薦一部戀愛／校園系動漫🎬")
async def anime(ctx):
    await ctx.respond("推薦中，請稍候...")

    max_retry = 5

    for _ in range(max_retry):
        result = await generate_anime_title()

        if not result:
            continue

        zh_name, jp_name = result

        # 避免推薦重複
        if jp_name in anime_history:
            continue

        anime_info = await search_jikan_anime(jp_name)

        if anime_info:
            # 再過濾一次人氣：比如MAL上至少有5000人收藏，但不要超過500,000
            if 5000 < anime_info["members"] < 4000000:
                anime_history.add(jp_name)
                embed = discord.Embed(
                    title=f"推薦作品名：{zh_name}｜{jp_name}",
                    url=anime_info["url"],
                    description="推薦給你的戀愛或校園番！",
                    color=0x00ccff
                )
                embed.set_image(url=anime_info["image_url"])

                await ctx.send(embed=embed)
                return
        
        await asyncio.sleep(1)  # 避免請求過快

    await ctx.send("找不到符合條件的作品，請再試一次。")


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

