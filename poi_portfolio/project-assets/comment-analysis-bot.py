# -*- coding: utf-8 -*-

import re
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from googleapiclient.discovery import build
from collections import Counter
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import requests

nltk.download('vader_lexicon')

# API keys and tokens were removed from this public portfolio version.
BOT_TOKEN = 'REDACTED_TELEGRAM_BOT_TOKEN'
YOUTUBE_API_KEY = 'REDACTED_YOUTUBE_API_KEY'
VK_ACCESS_TOKEN = 'REDACTED_VK_ACCESS_TOKEN'
VK_API_VERSION = '5.131'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
sentiment = SentimentIntensityAnalyzer()


def extract_youtube_video_id(url):
    match = re.search(r'(?:v=|youtu\.be/|shorts/)([\w-]+)', url)
    return match.group(1) if match else None


def fetch_youtube_comments(video_id, max_results=200):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    comments = []
    request = youtube.commentThreads().list(
        part='snippet',
        videoId=video_id,
        maxResults=min(max_results, 100),
        textFormat='plainText'
    )
    while request:
        response = request.execute()
        for item in response['items']:
            snippet = item['snippet']['topLevelComment']['snippet']
            comments.append({
                'text': snippet.get('textDisplay', ''),
                'likeCount': snippet.get('likeCount', 0),
                'replies': item['snippet'].get('totalReplyCount', 0)
            })
        request = youtube.commentThreads().list_next(request, response)
        if len(comments) >= max_results:
            break
    return comments


def extract_vk_post_info(url):
    m = re.search(r'wall(-?\d+)_(\d+)', url)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def fetch_vk_comments(url, max_results=200):
    owner_id, post_id = extract_vk_post_info(url)
    if owner_id is None or post_id is None:
        return []

    comments = []
    count = 100
    offset = 0
    while len(comments) < max_results:
        params = {
            'owner_id': owner_id,
            'post_id': post_id,
            'need_likes': 1,
            'count': min(count, max_results - len(comments)),
            'offset': offset,
            'access_token': VK_ACCESS_TOKEN,
            'v': VK_API_VERSION
        }
        resp = requests.get('https://api.vk.com/method/wall.getComments', params=params).json()
        if 'error' in resp:
            break
        items = resp.get('response', {}).get('items', [])
        if not items:
            break
        for c in items:
            comments.append({
                'text': c.get('text', ''),
                'likeCount': c.get('likes', {}).get('count', 0),
                'replies': c.get('thread', {}).get('count', 0)
            })
        if len(items) < count:
            break
        offset += count
    return comments


def is_spam(text):
    text = text.lower()
    return bool(re.search(r'подпишись|бесплатно|http|t\.me/', text))


def is_bot_like(text):
    text = text.lower()
    return len(text) < 6 or text.count('🔥') > 2 or len(set(text.split())) <= 2 or bool(re.match(r'https?://', text))


def analyze_comments(comments):
    sentiment_sum = {'positive': 0, 'neutral': 0, 'negative': 0}
    bot_count = spam_count = human_count = total_likes = 0
    most_liked = sorted(comments, key=lambda x: x['likeCount'], reverse=True)[:5]
    most_replied = sorted(comments, key=lambda x: x['replies'], reverse=True)[:5]
    texts = [re.sub(r'\W+', ' ', c['text']).strip().lower() for c in comments]
    repeated = Counter(texts).most_common(5)
    brand_mentions = []

    for c in comments:
        t = c['text']
        total_likes += c['likeCount']
        if is_spam(t):
            spam_count += 1
        elif is_bot_like(t):
            bot_count += 1
        else:
            human_count += 1
            score = sentiment.polarity_scores(t)['compound']
            if score >= 0.05:
                sentiment_sum['positive'] += 1
            elif score <= -0.05:
                sentiment_sum['negative'] += 1
            else:
                sentiment_sum['neutral'] += 1
        if 'hochland' in t.lower():
            tone = sentiment.polarity_scores(t)['compound']
            polarity = 'позитив' if tone >= 0.05 else 'негатив' if tone <= -0.05 else 'нейтрал'
            brand_mentions.append({'text': t, 'tone': polarity})

    total = len(comments)
    return {
        'bot_pct': round(bot_count / total * 100, 2) if total else 0,
        'spam_pct': round(spam_count / total * 100, 2) if total else 0,
        'human_pct': round(human_count / total * 100, 2) if total else 0,
        'sentiment': sentiment_sum,
        'most_liked': most_liked,
        'most_replied': most_replied,
        'repeated': repeated,
        'brand_mentions': brand_mentions,
        'er': round(total_likes / human_count, 2) if human_count else 0
    }


@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer('Привет! Пришли ссылку на YouTube-видео или ВК-пост, чтобы я проанализировал комментарии.')


@dp.message()
async def handle_link(m: types.Message):
    url = m.text.strip()

    if 'youtu' in url:
        video_id = extract_youtube_video_id(url)
        if not video_id:
            return await m.answer('Не удалось распознать YouTube ссылку.')
        await m.answer('🔄 Анализирую комментарии YouTube...')
        comments = fetch_youtube_comments(video_id)
    elif 'vk.com' in url:
        await m.answer('🔄 Анализирую комментарии ВКонтакте...')
        comments = fetch_vk_comments(url)
        if not comments:
            return await m.answer('Не удалось получить комментарии ВКонтакте.')
    else:
        return await m.answer('Нужна ссылка на YouTube или ВК.')

    if not comments:
        return await m.answer('Комментариев нет или они отключены.')

    res = analyze_comments(comments)
    s = res['sentiment']
    report = (
        f"🙋 Живые: {res['human_pct']}%  🤖 Боты: {res['bot_pct']}%  📢 Спам: {res['spam_pct']}%\n\n"
        f"🧠 Тональность (живые): +{s['positive']}  😐{s['neutral']}  -{s['negative']}\n"
        f"📈 ER (лайков/жизн.): {res['er']}\n\n"
        f"🔥 ТОП-лайки:\n" + "\n".join(
            f"• {c['text'][:60]}… ({c['likeCount']}❤️)" for c in res['most_liked']) + "\n\n"
        f"🧵 ТОП-обсуждения:\n" + "\n".join(
            f"• {c['text'][:60]}… ({c['replies']} ответов)" for c in res['most_replied']) + "\n\n"
        f"🔁 Повторы:\n" + "\n".join(
            f"• {t[:60]}… ({cnt} раз)" for t, cnt in res['repeated']) + "\n\n"
    )
    if res['brand_mentions']:
        report += '🔎 Упоминания Hochland:\n'
        for bm in res['brand_mentions']:
            report += f"• ({bm['tone']}) {bm['text'][:100]}…\n"

    await m.answer(report[:4096])


if __name__ == '__main__':
    asyncio.run(dp.start_polling(bot))
