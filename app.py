from flask import Flask, request, jsonify
import os, json, traceback
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import gspread.exceptions as GSE

# ---- Config flags ----
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() in ("true", "1", "yes")

# ---- Google auth via Render env var ----
creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = Credentials.from_service_account_info(
    creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(creds)

app = Flask(__name__)

@app.route("/healthz")
def healthz():
    return "ok", 200

@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        data = request.get_json(force=True)
        blog_url = data.get("blog_url")
        spreadsheet_id = data.get("spreadsheet_id")
        if not blog_url or not spreadsheet_id:
            return jsonify({"error": "Missing blog_url or spreadsheet_id"}), 400

        # --- Fetch blog page ---
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0 Safari/537.36"
        }
        r = requests.get(blog_url, headers=headers, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # --- Extract posts ---
        posts = []
        for idx, article in enumerate(soup.select("article")):
            h2 = article.find("h2") or article.find("h1")
            title = h2.get_text(strip=True) if h2 else "Untitled"
            body = article.get_text(" ", strip=True)[:20000]
            date = ""
            posts.append([title, body, date, blog_url])

            if TEST_MODE:  # 🔥 stop after first post if test mode enabled
                break

        # --- Write to Google Sheets ---
        sh = gc.open_by_key(spreadsheet_id)
        try:
            ws = sh.worksheet("Source")
        except GSE.WorksheetNotFound:
            ws = sh.add_worksheet(title="Source", rows=100, cols=4)

        ws.clear()
        ws.append_row(["Title", "Body", "Date", "URL"])
        if posts:
            ws.append_rows(posts, value_input_option="RAW")

        return jsonify({"status": "ok", "count": len(posts)}), 200

    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
