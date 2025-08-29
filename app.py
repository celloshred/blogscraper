from flask import Flask, request, jsonify
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup
import os, json

app = Flask(__name__)

# ---- Auth: env var JSON for service account ----
creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = Credentials.from_service_account_info(
    creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(creds)

@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        data = request.get_json(force=True) or {}
        blog_url = data.get("blog_url")
        spreadsheet_id = data.get("spreadsheet_id")
        max_results = int(data.get("max_results", 50))  # <= limit how many posts to process

        if not blog_url or not spreadsheet_id:
            return jsonify({"error": "Missing blog_url or spreadsheet_id"}), 400
        if max_results < 1:
            return jsonify({"error": "max_results must be >= 1"}), 400

        # Fetch the page
        r = requests.get(
            blog_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (BlogScraper/1.0)"},
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Parse posts (limit with max_results)
        posts = []
        for article in soup.select("article")[:max_results]:
            title = article.find("h2").get_text(strip=True) if article.find("h2") else "Untitled"
            body  = article.get_text(strip=True)[:20000]  # keep reasonable cap
            date  = ""
            posts.append([title, body, date, blog_url])

        # Sheets auth from env (unchanged)
        import os, json
        from google.oauth2.service_account import Credentials
        creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
        creds = Credentials.from_service_account_info(
            creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        gc = gspread.authorize(creds)

        # Write to "Source"
        sh = gc.open_by_key(spreadsheet_id)
        try:
            ws = sh.worksheet("Source")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="Source", rows=100, cols=4)

        ws.clear()
        ws.append_row(["Title", "Body", "Date", "URL"])
        if posts:
            ws.append_rows(posts, value_input_option="RAW")

        return jsonify({"status": "ok", "count": len(posts)}), 200

    except requests.HTTPError as e:
        return jsonify({"error": f"HTTP {e.response.status_code}", "detail": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "detail": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
