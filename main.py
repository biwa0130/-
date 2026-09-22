import os
import random
import datetime
import schedule
import time
import threading
import MeCab
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    TextMessage,
    ReplyMessageRequest,
    PushMessageRequest
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

# ==========================================
# ★設定情報
# ==========================================
CHANNEL_ACCESS_TOKEN = '5b146DjwZw7Si+3sjKoBK4ON51lduHm5Ec2SXN9dYvyJ6O3g/26UrxXJc+N8ggmoE6+boxOqPoOrhZJr5+NNreEFwCzo7t8ntqV96Dg5RoFZAaOxlYcCQSiboAfHjf4IphYjlquVVIUswseB1N7TtAdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = 'ad33482b5a6a9b942f689c68e4fd87b1'

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
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

    markov = {}
    for i in range(len(words) - 2):
        w1, w2, w3 = words[i], words[i+1], words[i+2]
        if (w1, w2) not in markov:
            markov[(w1, w2)] = []
        markov[(w1, w2)].append(w3)

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
    try:
        if os.path.exists(GROUP_ID_FILE):
            with open(GROUP_ID_FILE, "r") as f:
                group_id = f.read().strip()
            
            if group_id:
                message_text = generate_adachi_text()
                with ApiClient(configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    line_bot_api.push_message(
                        PushMessageRequest(
                            to=group_id,
                            messages=[TextMessage(text=message_text)]
                        )
                    )
                print("ランダム自動ツイートを送信しました！")
    except Exception as e:
        print(f"自動ツイート送信エラー: {e}")

def schedule_random_time():
    random_hour = random.randint(9, 19)
    random_minute = random.randint(0, 59)
    time_str = f"{random_hour:02d}:{random_minute:02d}"
    print(f"本日の自動ツイート予定時刻は 【{time_str}】 です！")
    
    schedule.clear('daily_job')
    schedule.every().day.at(time_str).do(daily_tweet).tag('daily_job')

schedule.every().day.at("00:00").do(schedule_random_time)
schedule_random_time()

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

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    if event.source.type == 'group':
        group_id = event.source.group_id
        with open(GROUP_ID_FILE, "w") as f:
            f.write(group_id)
        print(f"\n【取得完了】グループIDを記録しました: {group_id}\n")

    if "足立レイ" in event.message.text:
        reply_text = generate_adachi_text()
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

# --- 4. 起動処理 ---
if __name__ == "__main__":
    t = threading.Thread(target=run_schedule)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
