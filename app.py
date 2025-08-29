from flask import Flask, request, jsonify
import os, json, requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# --- Auth from env (Render Environment Variable GOOGLE_CREDS) ---
creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = Credentials.from_service_account_info(
    creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(creds)

@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        data = request.get_json(force=True)
        blog_url       = data.get("blog_url")
        spreadsheet_id = data.get("spreadsheet_id")
        limit          = int(data.get("limit", 5))  # cap how many posts we load

        if not blog_url or not spreadsheet_id:
            return jsonify({"error": "Missing blog_url or spreadsheet_id"}), 400

        # --- fetch page ---
        r = requests.get(
            blog_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; blog-scraper/1.0)"}
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # --- extract posts (very simple example; adjust selectors to your site) ---
        posts = []
        for art in soup.select("article")[:limit]:
            title = art.find("h1") or art.find("h2")
            title = title.get_text(strip=True) if title else "Untitled"
            body  = art.get_text(" ", strip=True)
            date  = ""
            posts.append([title, body, date, blog_url])

        # --- write to Sheets with gspread (no get_last_row here) ---
        sh = gc.open_by_key(spreadsheet_id)
        try:
            ws = sh.worksheet("Source")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="Source", rows=200, cols=4)

        # clear then write header and rows
        ws.clear()
        ws.update("A1:D1", [["Title", "Body", "Date", "URL"]])
        if posts:
            ws.update(f"A2:D{1+len(posts)}", posts)

        return jsonify({"status": "ok", "count": len(posts)})

    except Exception as e:
        # bubble a clean error message so your Apps Script can log it
        return jsonify({"error": str(e), "server_error": True}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
