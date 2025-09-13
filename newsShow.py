from flask import Flask, render_template_string, request, Response, jsonify, stream_with_context
import feedparser
from datetime import datetime, timedelta, timezone
import email.utils
import os
import concurrent.futures
import time

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
body { font-family: Arial, sans-serif; background:#f4f6f9; margin:0; padding:0; }
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
.progress-container {text-align:center; margin-top:10px;}
progress {width:80%; height:20px;}
.loading {text-align:center; font-size:1rem; margin-top:10px; color:#555;}
.no-news {text-align:center; font-size:1.1rem; color:#555; margin-top:20px;}
@media(max-width:600px){header{font-size:1.2rem;}}
</style>
</head>
<body>

<header>NewsShow App</header>

<div class="controls">
<input type="text" id="keyword" placeholder="Enter keyword (location, person, party...)" value="{{ keyword }}">
<button onclick="searchNews()">Search</button>
</div>

<div class="progress-container">
<progress id="progressBar" value="0" max="100" style="display:none;"></progress>
<div id="progressText"></div>
</div>

<div id="news-container">
<div class="loading">Loading news for "{{ keyword }}"...</div>
</div>

<script>
function searchNews(){
    let keyword=document.getElementById("keyword").value;
    if(!keyword) keyword="Mumbai";
    document.getElementById("progressBar").style.display="block";
    document.getElementById("progressBar").value=0;
    document.getElementById("progressText").innerText="Starting...";
    document.getElementById("news-container").innerHTML="";
    
    // SSE for progress
    const evtSource = new EventSource(`/api/news-progress?keyword=${encodeURIComponent(keyword)}`);
    let newsData=[];
    evtSource.onmessage=function(e){
        if(e.data.startsWith("PROGRESS:")){
            let val=parseInt(e.data.replace("PROGRESS:",""));
            document.getElementById("progressBar").value=val;
            document.getElementById("progressText").innerText=`Fetching feeds: ${val}%`;
        }else if(e.data.startsWith("DONE:")){
            evtSource.close();
            newsData=JSON.parse(e.data.replace("DONE:",""));
            document.getElementById("progressBar").style.display="none";
            renderNews(newsData);
        }else if(e.data.startsWith("ERROR:")){
            console.error(e.data);
        }
    };
    evtSource.onerror=function(){
        document.getElementById("progressText").innerText="Error fetching news!";
        evtSource.close();
    };
}

function renderNews(news){
    let html="";
    if(news.length>0){
        html+='<div class="container">';
        news.forEach(n=>{
            html+='<div class="card">';
            if(n.image) html+=`<img src="${n.image}">`;
            html+=`<div class="title">${n.title}</div>`;
            html+=`<div class="source">Source: ${n.source}</div>`;
            html+=`<div class="meta">${n.date}</div>`;
            html+=`<a class="link" href="${n.link}" target="_blank">More...</a>`;
            html+='</div>';
        });
        html+='</div>';
    }else{
        html=`<div class="no-news">No news found in the last 24 hours.</div>`;
    }
    document.getElementById("news-container").innerHTML=html;
}

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

def fetch_feed(source,url,keyword,yesterday):
    news=[]
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
                except:
                    parsed_date=datetime.now(timezone.utc)
                if parsed_date<yesterday: continue
                date_str=parsed_date.strftime("%Y-%m-%d %H:%M")
            else: date_str=""
            news.append({"title":entry.title,"link":entry.link,"date":date_str,"source":source,"image":img_url})
    except Exception as e:
        news.append({"title":f"Error fetching {source}: {e}","link":"","date":"","source":source,"image":""})
    return news

@app.route("/api/news-progress")
def api_news_progress():
    keyword=request.args.get("keyword","Mumbai").strip() or "Mumbai"
    now=datetime.now(timezone.utc)
    yesterday=now - timedelta(days=1)
    all_news=[]
    sources=list(RSS_FEEDS.items())
    total=len(sources)+1  # including Google News
    completed=0

    def generate():
        nonlocal completed, all_news
        # Google News
        try:
            query="+".join(keyword.split())
            google_rss=f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
            feed=feedparser.parse(google_rss)
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
        except Exception as e:
            yield f"data: ERROR:Google News failed: {e}\n\n"
        completed+=1
        yield f"data: PROGRESS:{int(completed/total*100)}\n\n"

        # Parallel RSS feeds
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures={executor.submit(fetch_feed, src,url,keyword,yesterday): src for src,url in sources}
            for future in concurrent.futures.as_completed(futures):
                src=futures[future]
                try:
                    result=future.result()
                    all_news.extend(result)
                except Exception as e:
                    yield f"data: ERROR:{src} failed: {e}\n\n"
                completed+=1
                yield f"data: PROGRESS:{int(completed/total*100)}\n\n"

        all_news.sort(key=lambda x:x["date"],reverse=True)
        yield f"data: DONE:{jsonify(all_news).get_data(as_text=True)}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE,news_items=[],keyword="Mumbai")

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=False)
