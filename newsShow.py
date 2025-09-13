from flask import Flask, render_template_string, request
import feedparser
from datetime import datetime, timedelta, timezone
import email.utils
import os

app = Flask(__name__)

RSS_FEEDS = {
    "Times of India": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "Indian Express": "https://indianexpress.com/feed/",
    "Hindustan Times": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
    "PTI": "https://www.ptinews.com/rss/pti.xml",
    "ANI": "https://www.aninews.in/rssfeed.aspx?cat=home",
    "Mid-Day": "https://www.mid-day.com/rss-feed",
    "Mumbai Live": "https://www.mumbailive.com/en/rss",
    "Free Press Journal": "https://www.freepressjournal.in/rss",
    "Mumbai Mirror": "https://mumbaimirror.indiatimes.com/rss.cms"
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NewsShow App</title>
<style>
body { font-family: Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 0; }
header { background: #1e3c72; color: white; padding: 15px; text-align: center; font-size: 1.5rem; font-weight: bold; }
.controls { display: flex; justify-content: center; align-items: center; padding: 15px; background: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
.controls input { padding: 8px 12px; font-size: 1rem; border: 1px solid #ccc; border-radius: 6px; width: 220px; margin-right: 10px; }
.controls button { padding: 8px 12px; font-size: 1rem; border-radius: 6px; background: #1e3c72; color: white; border: none; cursor: pointer; }
.controls button:hover { background: #2a5298; }
.container { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; padding: 20px; }
.card { background: white; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); padding: 20px; display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.2s; }
.card:hover { transform: translateY(-5px); }
.title { font-size: 1.2rem; font-weight: bold; margin-bottom: 10px; color: #1e3c72; }
.source { font-size: 0.9rem; color: #666; margin-bottom: 8px; }
.meta { font-size: 0.85rem; color: #777; margin-bottom: 10px; }
.link { text-decoration: none; background: #1e3c72; color: white; padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; text-align: center; transition: background 0.3s; }
.link:hover { background: #2a5298; }
@media (max-width: 600px) { header { font-size: 1.2rem; } }
</style>
</head>
<body>

<header>NewsShow App</header>

<form class="controls" method="GET" action="/">
<input type="text" name="keyword" placeholder="Enter keyword (location, person, party...)" value="{{ keyword }}">
<button type="submit">Search</button>
</form>

<div class="container">
{% for news in news_items %}
<div class="card">
<div class="title">{{ news.title }}</div>
<div class="source">Source: {{ news.source }}</div>
<div class="meta">{{ news.date }}</div>
<a class="link" href="{{ news.link }}" target="_blank">More...</a>
</div>
{% endfor %}
</div>

</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    keyword = request.args.get("keyword", "").strip()
    all_news = []
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    if keyword:
        # Google News RSS
        query = "+".join(keyword.split())
        google_rss = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(google_rss)
        for entry in feed.entries[:50]:
            if "published" in entry:
                parsed_date = email.utils.parsedate_to_datetime(entry.published)
                if parsed_date.tzinfo is None:
                    parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                if parsed_date < yesterday:
                    continue
                date_str = parsed_date.strftime("%Y-%m-%d %H:%M")
            else:
                date_str = ""
            all_news.append({
                "title": entry.title,
                "link": entry.link,
                "date": date_str,
                "source": "Google News"
            })

        # Additional RSS feeds
        for source, url in RSS_FEEDS.items():
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                combined_text = entry.title + (" " + entry.summary if "summary" in entry else "")
                if keyword.lower() not in combined_text.lower():
                    continue
                if "published" in entry:
                    try:
                        parsed_date = email.utils.parsedate_to_datetime(entry.published)
                        if parsed_date.tzinfo is None:
                            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                    except:
                        parsed_date = now
                    if parsed_date < yesterday:
                        continue
                    date_str = parsed_date.strftime("%Y-%m-%d %H:%M")
                else:
                    date_str = ""
                all_news.append({
                    "title": entry.title,
                    "link": entry.link,
                    "date": date_str,
                    "source": source
                })

    # Sort by date descending
    all_news.sort(key=lambda x: x["date"], reverse=True)
    return render_template_string(HTML_TEMPLATE, news_items=all_news, keyword=keyword)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
