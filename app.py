from flask import Flask, request, jsonify
import gspread
from google.oauth2.service_account import Credentials
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route("/scrape", methods=["POST"])
def scrape():
    data = request.json
    blog_url = data.get("blog_url")
    spreadsheet_id = data.get("spreadsheet_id")

    if not blog_url or not spreadsheet_id:
        return jsonify({"error": "Missing blog_url or spreadsheet_id"}), 400

    # Fetch blog page
    r = requests.get(blog_url)
    soup = BeautifulSoup(r.text, "html.parser")

    # Example: grab <article> blocks
    posts = []
    for article in soup.select("article"):
        title = article.find("h2").get_text(strip=True) if article.find("h2") else "Untitled"
        body  = article.get_text(strip=True)[:2000]  # limit for demo
        date  = ""
        posts.append([title, body, date, blog_url])

    # Connect to Google Sheets
    creds = Credentials.from_service_account_file("service.json", scopes=[
        "https://www.googleapis.com/auth/spreadsheets"
    ])
    client = gspread.authorize(creds)

    sh = client.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet("Source")
    except:
        ws = sh.add_worksheet(title="Source", rows=100, cols=4)

    ws.clear()
    ws.append_row(["Title", "Body", "Date", "URL"])
    for row in posts:
        ws.append_row(row)

    return jsonify({"status": "ok", "count": len(posts)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
