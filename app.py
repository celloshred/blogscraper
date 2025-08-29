from flask import Flask, request, jsonify
import os, json, requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import traceback

app = Flask(__name__)

# --- Auth from env: GOOGLE_CREDS (full service account JSON) ---
try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
    creds = Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    print("Google Sheets authentication successful")
except Exception as e:
    print(f"Authentication error: {e}")
    gc = None

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "blog-scraper"})

@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        # Check if authentication is available
        if not gc:
            return jsonify({"error": "Google Sheets authentication failed"}), 500
        
        data = request.get_json(force=True)
        blog_url       = data.get("blog_url")
        spreadsheet_id = data.get("spreadsheet_id")
        limit          = int(data.get("limit", 5))

        print(f"Processing request: blog_url={blog_url}, spreadsheet_id={spreadsheet_id}, limit={limit}")

        if not blog_url or not spreadsheet_id:
            return jsonify({"error": "Missing blog_url or spreadsheet_id"}), 400

        # --- fetch page ---
        print(f"Fetching blog content from: {blog_url}")
        r = requests.get(
            blog_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; blog-scraper/1.0)"}
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        print("Successfully fetched and parsed blog content")

        # --- extract posts ---
        posts = []
        articles = soup.select("article")
        print(f"Found {len(articles)} article elements")
        
        for i, art in enumerate(articles[:limit]):
            # Try multiple heading selectors
            h = (art.find("h1") or art.find("h2") or art.find("h3") or 
                 art.find("h4") or art.find(class_="title") or art.find(class_="post-title"))
            
            title = h.get_text(strip=True) if h else f"Post {i+1}"
            body = art.get_text(" ", strip=True)[:500]  # Limit body length
            
            # Extract individual post URL
            post_url = blog_url  # fallback to main blog URL
            
            # Look for links in the article
            link = (art.find("a", href=True) or 
                   (h.find("a", href=True) if h else None))
            
            if link and link.get("href"):
                href = link["href"]
                # Make relative URLs absolute
                if href.startswith("/"):
                    from urllib.parse import urljoin
                    post_url = urljoin(blog_url, href)
                elif href.startswith("http"):
                    post_url = href
            
            date = ""  # Could extract date if needed
            posts.append([title, body, date, post_url])
            print(f"Extracted post {i+1}: {title[:50]}... URL: {post_url}")

        print(f"Successfully extracted {len(posts)} posts")

        # --- write to Google Sheet ---
        print(f"Opening spreadsheet: {spreadsheet_id}")
        sh = gc.open_by_key(spreadsheet_id)
        
        try:
            ws = sh.worksheet("Source")
            print("Found existing Source worksheet")
        except gspread.exceptions.WorksheetNotFound:
            print("Creating new Source worksheet")
            ws = sh.add_worksheet(title="Source", rows=200, cols=4)

        # Clear and update
        print("Clearing worksheet and adding headers")
        ws.clear()
        ws.update("A1:D1", [["Title", "Body", "Date", "URL"]])
        
        if posts:
            end_row = 1 + len(posts)
            print(f"Writing {len(posts)} posts to range A2:D{end_row}")
            ws.update(f"A2:D{end_row}", posts)

        print(f"Successfully processed {len(posts)} posts")
        return jsonify({"status": "ok", "count": len(posts)})

    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to fetch blog content: {str(e)}"
        print(error_msg)
        return jsonify({"error": error_msg, "server_error": True}), 500
    
    except gspread.exceptions.APIError as e:
        error_msg = f"Google Sheets API error: {str(e)}"
        print(error_msg)
        return jsonify({"error": error_msg, "server_error": True}), 500
    
    except Exception as e:
        error_msg = str(e)
        print(f"Unexpected error: {error_msg}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": error_msg, 
            "server_error": True,
            "traceback": traceback.format_exc()
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
