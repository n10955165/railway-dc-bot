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
        await text_channel.send(f"⚠️找不到適合的曲子呢：\n```{traceback.format_exc()}```")



# ====== イベント ======
@bot.event
async def on_ready():
    print(f"✅ 起動完成！！！: {bot.user}")

# ====== スラッシュコマンド：兄控チャット ======
@bot.slash_command(name="onichan", description="和妹妹説個話吧~")
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
        await ctx.send(f"💔 啊，好像出錯了…：{e}")

# ====== スラッシュコマンド：Vocaloid曲再生 ======
# ====== 歷史記憶（全域變數）======
recent_songs = []

@bot.slash_command(name="play", description="妹妹會爲你選擇Vocaloid歌曲哦~~🎵")
async def play(ctx):
    global recent_songs

    await ctx.respond("嗯……我一定會找一首適合哥哥的曲子的……💗")

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
                await ctx.send("呃嘿嘿...我好像忘了歌名了...再說一次吧~💦")
                return

            # 如果曲子還是重複，直接告知
            if song_title in recent_songs:
                await ctx.send("唔…好像又要變成同樣的歌了…我會再試一次的💦")
                return

            # 記住這首歌
            recent_songs.append(song_title)
            if len(recent_songs) > 10:
                recent_songs.pop(0)  # 保持只記錄10首

            await play_youtube(song_title, ctx.channel)

        else:
            await ctx.send("呃嘿嘿...我好像忘了歌名了...再說一次吧~💦")

    except Exception as e:
        await ctx.send(f"💔 哥哥~對不起…👉🏻👈🏻：{e}")

anime_history = set()

# AI 生成推薦動漫
async def generate_anime_title():
    prompt = (
        "以下の條件でアニメを一作品推薦してください：\n"
        "・ジャンルは『戀愛番』か『校園番』。\n"
        "・放送は2010年以降。\n"
        "・格式は：『推薦作品名：<繁體中文名>｜<日文名>』または『<日文名>』。"
    )
    ai_response = model.generate_content(prompt)
    text = ai_response.text.strip()

    # 最寬鬆處理方式
    if "推薦作品名：" in text and "｜" in text:
        parts = text.split("推薦作品名：")[1].split("｜")
        zh_name = parts[0].strip()
        jp_name = parts[1].strip()
        return zh_name, jp_name
    elif "｜" in text:
        zh_name, jp_name = text.split("｜")
        return zh_name.strip(), jp_name.strip()
    else:
        return None, text  # 把整段當作日文名 fallback 使用

# Jikan API 搜尋
async def search_jikan_anime(title_jp):
    url = f"https://api.jikan.moe/v4/anime?q={title_jp}&limit=10&sfw=true"
    res = requests.get(url)

    if res.status_code != 200:
        return None

    data = res.json()
    if not data.get("data"):
        return None

    for anime in data["data"]:
        year = anime.get("year", 0)
        genres = [g["name"] for g in anime.get("genres", [])]

        # 寬鬆條件：2010以後 + 含任一關鍵 genre
        if year >= 2010 and ("Romance" in genres or "School" in genres):
            return {
                "title_jp": anime.get("title_japanese", anime.get("title")),
                "title_zh": anime.get("title"),
                "url": anime["url"],
                "image_url": anime["images"]["jpg"]["large_image_url"]
            }

    return None

@bot.slash_command(name="anime", description="推薦一部戀愛／校園系動漫")
async def anime(ctx):
    await ctx.respond("讓我找一下呦~")

    for _ in range(5):  # retry 最多 5 次
        result = await generate_anime_title()
        if not result:
            continue

        zh_name, jp_name = result

        if jp_name in anime_history:
            continue

        anime_info = await search_jikan_anime(jp_name)

        if anime_info:
            anime_history.add(jp_name)
            embed = discord.Embed(
                title=f"推薦作品名：{anime_info['title_zh']}｜{anime_info['title_jp']}",
                url=anime_info["url"],
                color=0x00ccff
            )
            embed.set_image(url=anime_info["image_url"])
            await ctx.send(embed=embed)
            return

        await asyncio.sleep(1)

    await ctx.send("我找不到符合條件的作品👉🏻👈🏻，還是讓我再試一次看看？")




# ====== 天氣查詢指令（改良版） ======
@bot.slash_command(name="weather", description="妹妹會告訴你天氣呦☀️")
async def weather(ctx, city: Option(str, "どこの天気を知りたい？（都市名を入力してね）")):
    await ctx.respond("哥哥…要等一下呦…💖")

    weather_api_key = os.getenv("WEATHER_API_KEY")
    url = f"http://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={city}&lang=ja"

    try:
        response = requests.get(url)
        data = response.json()

        if "error" in data:
            await ctx.send(f"呃……我好像找不到那個地方💦\n（エラー：{data['error']['message']}）")
            return

        # 拿資料
        temp_c = data['current']['temp_c']
        condition = data['current']['condition']['text']
        humidity = data['current']['humidity']


        # 發送訊息
        message = (
            f"哥哥，這是今天**{city}**的天氣喲～☀️\n"
            f"🌡️ 氣温：**{temp_c}°C**\n"
            f"☁️ 狀態：**{condition}**\n"
            f"💧 溼度：**{humidity}%**\n\n"
        )

        await ctx.send(message)

    except Exception as e:
        await ctx.send(f"💔 對不起，哥哥…我在查天氣的時候出錯了👉🏻👈🏻：{e}")

# ====== スラッシュコマンド：じゃんけん（猜拳） ======
@bot.slash_command(name="rps", description="和妹妹一起猜拳吧~~✊✌️🖐️")
async def rps(ctx, 手: Option(str, "哥哥選擇要出什麼吧~~", choices=["石頭", "剪刀", "布"])):
    await ctx.respond("嘿嘿……哥哥，我懂你在想什麼呦~💖")

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
            result = "平手呢~~💖（平手）"
        elif (手 == "グー" and ai_hand == "パー") or (手 == "チョキ" and ai_hand == "グー") or (手 == "パー" and ai_hand == "チョキ"):
            result = "嘿嘿~我贏啦~💖"
        else:
            result = "吼呦~~哥哥欺負我~~"

        await ctx.send(f"✊✌️🖐️\n哥哥出【{手}】、我出【{ai_hand}】哦~~！\n\n{result}")

    except Exception as e:
        await ctx.send(f"💔 哥哥~~對不起~~我腦袋當機了👉🏻👈🏻：{e}")

# ====== 普通のメッセージ反応（旧式） ======
@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.author == bot.user:
        return
    if message.content.startswith("!hello"):
        await message.channel.send("哥哥~你好呀~💖")

# ====== Bot起動 ======
bot.run(TOKEN)

