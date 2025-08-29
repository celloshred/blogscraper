from flask import Flask, request, jsonify
import os, json
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# ---- Auth: read service account JSON from Render env var ----
creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = Credentials.from_service_account_info(
    creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(creds)

app = Flask(__name__)

@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        data = request.get_json(force=True)  # ensure JSON
        blog_url = data.get("blog_url")
        spreadsheet_id = data.get("spreadsheet_id")

        if not blog_url or not spreadsheet_id:
            return jsonify({"error": "Missing blog_url or spreadsheet_id"}), 400

        # --- scrape ---
        r = requests.get(blog_url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        posts = []
        for article in soup.select("article"):
            title = article.find("h2").get_text(strip=True) if article.find("h2") else "Untitled"
            body  = article.get_text(strip=True)[:2000]
            date  = ""
            posts.append([title, body, date, blog_url])

        # --- write to Sheets ---
        sh = gc.open_by_key(spreadsheet_id)
        try:
            ws = sh.worksheet("Source")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="Source", rows=100, cols=4)

        ws.clear()
        ws.append_row(["Title", "Body", "Date", "URL"])
        if posts:
            ws.append_rows(posts, value_input_option="RAW")

        return jsonify({"status": "ok", "count": len(posts)})

    except Exception as e:
        # helpful error back to you
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
