from flask import Flask, render_template_string, request, Response
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
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#1e3c72">
<style>
body { font-family: Arial, sans-serif; background: #f4f6f9; margin:0; padding:0; }
header { background:#1e3c72; color:white; padding:15px; text-align:center; font-size:1.5rem; font-weight:bold; }
.controls { display:flex; justify-content:center; align-items:center; padding:15px; background:#fff; box-shadow:0 2px 5px rgba(0,0,0,0.1);}
.controls input {padding:8px 12px; font-size:1rem; border:1px solid #ccc; border-radius:6px; width:220px; margin-right:10px;}
.controls button {padding:8px 12px; font-size:1rem; border-radius:6px; background:#1e3c72; color:white; border:none; cursor:pointer;}
.controls button:hover {background:#2a5298;}
.container {display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:20px; padding:20px;}
.card {background:linear-gradient(135deg,#ffffff,#e8f0fe); border-left:5px solid #1e3c72; border-radius:12px; box-shadow:0 6px 15px rgba(0,0,0,0.15); padding:20px; display:flex; flex-direction:column; justify-content:space-between; transition:transform 0.3s,box-shadow 0.3s;}
.card:hover {transform:translateY(-8px); box-shadow:0 10px 25px rgba(0,0,0,0.2);}
.card img {width:100%; border-radius:8px; margin-bottom:10px;}
.title {font-size:1.2rem; font-weight:bold; margin-bottom:10px; color:#1e3c72;}
.source {font-size:0.9rem; color:#666; margin-bottom:8px;}
.meta {font-size:0.85rem; color:#777; margin-bottom:10px;}
.link {text-decoration:none; background:#1e3c72; color:white; padding:8px 12px; border-radius:6px; font-size:0.9rem; text-align:center; transition:background 0.3s;}
.link:hover {background:#2a5298;}
.no-news {text-align:center; font-size:1.1rem; color:#555; margin-top:20px;}
@media(max-width:600px){header{font-size:1.2rem;}}
</style>
</head>
<body>

<header>NewsShow App</header>

<form class="controls" method="GET" action="/">
<input type="text" name="keyword" placeholder="Enter keyword (location, person, party...)" value="{{ keyword }}">
<button type="submit">Search</button>
</form>

{% if news_items %}
<div class="container">
{% for news in news_items %}
<div class="card">
{% if news.image %}<img src="{{ news.image }}">{% endif %}
<div class="title">{{ news.title }}</div>
<div class="source">Source: {{ news.source }}</div>
<div class="meta">{{ news.date }}</div>
<a class="link" href="{{ news.link }}" target="_blank">More...</a>
</div>
{% endfor %}
</div>
{% else %}
<div class="no-news">No news found for "{{ keyword }}" in the last 24 hours.</div>
{% endif %}

<script>
if('serviceWorker' in navigator){
navigator.serviceWorker.register('/service-worker.js').then(reg=>console.log('Service Worker registered',reg)).catch(err=>console.log('Service Worker failed',err));
}
</script>

</body>
</html>
"""

MANIFEST_JSON = """
{
"name": "NewsShow App",
"short_name": "NewsShow",
"start_url": "/",
"display": "standalone",
"background_color": "#f4f6f9",
"theme_color": "#1e3c72",
"icons":[
{"src":"/static/icon-192.png","sizes":"192x192","type":"image/png"},
{"src":"/static/icon-512.png","sizes":"512x512","type":"image/png"}
]
}
"""

SERVICE_WORKER = """
const CACHE_NAME="newsshow-cache-v1";
const urlsToCache=["/"];
self.addEventListener("install",event=>{event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(urlsToCache)));});
self.addEventListener("fetch",event=>{event.respondWith(caches.match(event.request).then(response=>response||fetch(event.request)));});
"""

@app.route("/manifest.json")
def manifest():
    return Response(MANIFEST_JSON,mimetype='application/json')

@app.route("/service-worker.js")
def sw():
    return Response(SERVICE_WORKER,mimetype='application/javascript')

@app.route("/", methods=["GET"])
def index():
    keyword = request.args.get("keyword", "").strip() or "Mumbai"
    all_news=[]
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    # Google News
    try:
        query="+".join(keyword.split())
        google_rss=f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(google_rss)
        for entry in feed.entries[:30]:
            img_url=""
            if "media_content" in entry: img_url=entry.media_content[0]["url"]
            elif "media_thumbnail" in entry: img_url=entry.media_thumbnail[0]["url"]
            if "published" in entry:
                parsed_date=email.utils.parsedate_to_datetime(entry.published)
                if parsed_date.tzinfo is None: parsed_date=parsed_date.replace(tzinfo=timezone.utc)
                if parsed_date<yesterday: continue
                date_str=parsed_date.strftime("%Y-%m-%d %H:%M")
            else: date_str=""
            all_news.append({"title":entry.title,"link":entry.link,"date":date_str,"source":"Google News","image":img_url})
    except: pass

    # Other RSS feeds
    for source,url in RSS_FEEDS.items():
        try:
            feed=feedparser.parse(url)
            for entry in feed.entries[:15]:
                combined_text=entry.title+(" "+entry.summary if "summary" in entry else "")
                if keyword.lower() not in combined_text.lower(): continue
                img_url=""
                if "media_content" in entry: img_url=entry.media_content[0]["url"]
                elif "media_thumbnail" in entry: img_url=entry.media_thumbnail[0]["url"]
                if "published" in entry:
                    try:
                        parsed_date=email.utils.parsedate_to_datetime(entry.published)
                        if parsed_date.tzinfo is None: parsed_date=parsed_date.replace(tzinfo=timezone.utc)
                    except: parsed_date=now
                    if parsed_date<yesterday: continue
                    date_str=parsed_date.strftime("%Y-%m-%d %H:%M")
                else: date_str=""
                all_news.append({"title":entry.title,"link":entry.link,"date":date_str,"source":source,"image":img_url})
        except: continue

    all_news.sort(key=lambda x:x["date"],reverse=True)
    return render_template_string(HTML_TEMPLATE,news_items=all_news,keyword=keyword)

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=False)
