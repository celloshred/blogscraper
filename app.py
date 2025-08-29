from flask import Flask, request, jsonify
import os, json, traceback
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

def _gs_client():
    creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

def _ensure_ws(sh, name, cols=4):
    ws = sh.worksheet(name) if name in [w.title for w in sh.worksheets()] else sh.add_worksheet(name, rows=100, cols=cols)
    if ws.row_count == 0:
        ws.resize(rows=100, cols=cols)
    if ws.get_all_values() == [] or ws.get_last_row() == 0:
        ws.update("A1:D1", [["Title","Body","Date","URL"]])
    else:
        # ensure header exists
        vals = ws.get_values("A1:D1")
        if not vals or not vals[0] or vals[0][0] != "Title":
            ws.update("A1:D1", [["Title","Body","Date","URL"]])
    return ws

@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        data = request.get_json(force=True, silent=True) or {}
        blog_url = data.get("blog_url", "").strip()
        spreadsheet_id = data.get("spreadsheet_id", "").strip()
        max_posts = int(data.get("max_posts", 5))

        if not blog_url or not spreadsheet_id:
            return jsonify({"error":"missing_params"}), 400

        # Fetch page
        r = requests.get(blog_url, timeout=25, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        posts = []

        # Prefer multiple <article> blocks; fallback to single post
        articles = soup.select("article")
        if not articles:
            # single post fallback (H1 + content)
            h1 = soup.find(["h1","h2"])
            body_node = soup.find(attrs={"class":lambda x: x and "content" in x.lower()}) or soup.find("main") or soup
            title = h1.get_text(strip=True) if h1 else "Untitled"
            body = body_node.get_text(" ", strip=True)[:8000]
            posts.append([title, body, "", blog_url])
        else:
            for art in articles[:max_posts]:
                title = "Untitled"
                h2 = art.find(["h1","h2","h3"])
                if h2:
                    title = h2.get_text(strip=True)
                # strip scripts/navs
                for t in art.find_all(["script","style","nav","form"]):
                    t.decompose()
                body = art.get_text(" ", strip=True)[:8000]
                posts.append([title, body, "", blog_url])

        # Write to Google Sheets
        gc = _gs_client()
        sh = gc.open_by_key(spreadsheet_id)
        ws = _ensure_ws(sh, "Source")
        if len(posts):
            ws.append_rows(posts, value_input_option="RAW")

        return jsonify({"status":"ok", "count": len(posts)}), 200

    except Exception as e:
        # Log server-side to help debugging
        print("SERVER_ERROR:", str(e))
        print(traceback.format_exc())
        return jsonify({"error":"server_error", "detail": str(e)}), 500

if __name__ == "__main__":
    # Render uses gunicorn; this is for local test only.
    app.run(host="0.0.0.0", port=5000)
