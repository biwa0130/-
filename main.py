import os
import re
import random
import datetime
import schedule
import time
import threading
import MeCab
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# ==========================================
# ★設定情報
# ==========================================
CHANNEL_ACCESS_TOKEN = '5b146DjwZw7Si+3sjKoBK4ON51lduHm5Ec2SXN9dYvyJ6O3g/26UrxXJc+N8ggmoE6+boxOqPoOrhZJr5+NNreEFwCzo7t8ntqV96Dg5RoFZAaOxlYcCQSiboAfHjf4IphYjlquVVIUswseB1N7TtAdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = 'ad33482b5a6a9b942f689c68e4fd87b1'

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# グループID保存用ファイル
GROUP_ID_FILE = "group_id.txt"

# --- 1. マルコフ連鎖による文章生成機能 ---
def generate_adachi_text():
    if not os.path.exists("tweets_data.txt"):
        return "データファイルが見つかりません！"

    tagger = MeCab.Tagger("-Owakati")
    with open("tweets_data.txt", "r", encoding="utf-8") as f:
        text = f.read()

    words = tagger.parse(text).split()
    if len(words) < 3:
        return "データが足りません！"

    # マルコフ連鎖用の辞書作成
    markov = {}
    for i in range(len(words) - 2):
        w1, w2, w3 = words[i], words[i+1], words[i+2]
        if (w1, w2) not in markov:
            markov[(w1, w2)] = []
        markov[(w1, w2)].append(w3)

    # 文章生成
    first_pairs = [k for k in markov.keys() if k[0] not in ["。", "！", "？", "…"]]
    if not first_pairs:
        first_pairs = list(markov.keys())
    
    w1, w2 = random.choice(first_pairs)
    sentence = w1 + w2

    for _ in range(30):
        if (w1, w2) not in markov:
            break
        w3 = random.choice(markov[(w1, w2)])
        sentence += w3
        if w3 in ["。", "！", "？"] or len(sentence) > 80:
            break
        w1, w2 = w2, w3

    return sentence

# --- 2. ランダムな時間帯での自動つぶやき機能 ---
def daily_tweet():
    """実際にLINEのグループに自動つぶやきを送信する関数"""
    try:
        if os.path.exists(GROUP_ID_FILE):
            with open(GROUP_ID_FILE, "r") as f:
                group_id = f.read().strip()
            
            if group_id:
                message_text = generate_adachi_text()
                line_bot_api.push_message(
                    group_id,
                    TextSendMessage(text=message_text)
                )
                print("ランダム自動ツイートを送信しました！")
    except Exception as e:
        print(f"自動ツイート送信エラー: {e}")

def schedule_random_time():
    """朝9時〜夜20時の間でランダムな時間を毎日再設定する関数"""
    random_hour = random.randint(9, 19)
    random_minute = random.randint(0, 59)
    
    time_str = f"{random_hour:02d}:{random_minute:02d}"
    print(f"本日の自動ツイート予定時刻は 【{time_str}】 です！")
    
    schedule.clear('daily_job')
    schedule.every().day.at(time_str).do(daily_tweet).tag('daily_job')

# 毎日深夜0:00に「その日のランダムな時間」を新しく決め直す
schedule.every().day.at("00:00").do(schedule_random_time)
schedule_random_time() # 起動時にも設定

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(60)

# --- 3. LINE Webhook 処理 ---
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    if event.source.type == 'group':
        group_id = event.source.group_id
        with open(GROUP_ID_FILE, "w") as f:
            f.write(group_id)
        print(f"\n【取得完了】グループIDを記録しました: {group_id}\n")

    if "足立レイ" in event.message.text:
        reply_text = generate_adachi_text()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

# --- 4. 起動処理（バックグラウンド監視 ＆ Flaskサーバー） ---
if __name__ == "__main__":
    # スケジューラーを裏で動かすスレッド開始
    t = threading.Thread(target=run_schedule)
    t.daemon = True
    t.start()
    
    # Render用ポート設定でFlaskサーバー起動
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
