
import json
import re
import sys
import logging
from datetime import datetime
from urllib.parse import urlparse
from pymongo import MongoClient  # Import MongoClient

from bson import ObjectId # Make sure bson is installed (pip install pymongo)

# --- Configuration ---

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Suspicion Patterns ---

# Domains known for AI assistance
AI_DOMAINS = {
    "openai.com",        # Includes ChatGPT
    "chatgpt.com",
    "claude.ai",
    "anthropic.com",
    "gemini.google.com",
    "bard.google.com",
    "perplexity.ai",
    "blackbox.ai",       # AI code generation/search
    "phind.com",         # AI search for developers
}

# Domains known for coding solutions, forums, and tutorials
SOLUTION_DOMAINS = {
    "stackoverflow.com",
    "github.com",        # Can host solutions, needs context (keywords)
    "geeksforgeeks.org",
    "leetcode.com",      # Specifically check for /discuss/, solutions, or different problems
    "medium.com",        # Often hosts coding tutorials/solutions
    "dev.to",            # Blogging platform for developers
    "tutorialspoint.com",
    "w3schools.com",     # More foundational, less likely direct cheating
    "programiz.com",
    "chegg.com",         # Known for academic answers
    "coursehero.com",    # Known for academic answers
    # Add more specific platform discussion/solution URLs if needed
}

# General search engine domains
SEARCH_DOMAINS = {
    "google.com",
    "bing.com",
    "duckduckgo.com",
    "yahoo.com",
    "baidu.com",
    "yandex.com",
}

# Keywords often found in titles or URLs related to getting help/solutions
SUSPICIOUS_KEYWORDS = [
    "solution", "answer", "code", "solve", "cheat", "hack",
    "discussion", "discuss", "forum", "community", # Context dependent
    "tutorial", "guide", "example", "reference", # Can be legitimate learning
    "pastebin", "jsfiddle", "codepen", # Code sharing sites
    "gpt", "claude", "gemini", "bard", "ai", "llm", # AI terms
    "translate", # Sometimes used to understand problem statements from other languages or rephrase
]

# Keywords indicating legitimate activity within the coding platform
LEGITIMATE_PLATFORM_KEYWORDS = [
    "problems", "problemset", "list", "submissions", "contest", "profile",
    "explore", "ranking", "editorial", # Editorials *might* be disallowed during contests
]

# --- Scoring Weights ---
SCORE_WEIGHTS = {
    "TO_AI": 10,
    "TO_SOLUTION_DOMAIN_WITH_KEYWORDS": 8,
    "TO_SOLUTION_DOMAIN_GENERIC": 5, # e.g., main page of geeksforgeeks
    "TO_GITHUB_REPO": 6, # Possible solution repo
    "TO_SEARCH_ENGINE": 4,
    "TO_EXTERNAL_APPLICATION": 5, # Ambiguous intent
    "TO_SUSPICIOUS_KEYWORD_ONLY": 3, # Title/URL has keyword, domain not flagged
    "FROM_AI": 1, # Indicates they *were* on an AI site recently
    "FROM_SOLUTION": 1, # Indicates they *were* on a solution site recently
    "WITHIN_PLATFORM_TO_DIFFERENT_PROBLEM": 4, # Looking at other problems?
    "WITHIN_PLATFORM_TO_DISCUSSION": 6, # Looking at discussions?
}

MAX_SCORE = 10 # Cap the suspicion score

# --- Helper Functions ---

def get_domain(url):
    """Extracts the domain name (e.g., 'google.com') from a URL."""
    if not url or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
        return None
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        # Remove 'www.' prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain.lower()
    except ValueError:
        logging.warning(f"Could not parse URL: {url}")
        return None

def contains_keywords(text, keywords):
    """Checks if a string contains any of the specified keywords (case-insensitive)."""
    if not text or not isinstance(text, str):
        return False, None
    text_lower = text.lower()
    for keyword in keywords:
        # Use word boundaries to avoid partial matches (e.g., 'problemset' containing 'set')
        # But allow keywords like 'ai' or 'gpt' which might not have boundaries
        if len(keyword) <= 3 or re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_lower):
             return True, keyword
        # Fallback for short keywords or ones potentially attached to punctuation
        if keyword.lower() in text_lower:
             return True, keyword # Less precise match
    return False, None

def normalize_problem_identifier(problem_name_or_id):
    """Attempts to get a consistent identifier (like number or slug) from name/id."""
    if not problem_name_or_id: return None
    # Simple extraction: assumes ID might be numeric at start/end or name is descriptive
    match = re.match(r'^(\d+)', str(problem_name_or_id))
    if match: return match.group(1)
    # Could add more complex slug generation if needed
    return str(problem_name_or_id).lower().replace(" ", "-")


# --- Core Analysis Logic ---

def analyze_tab_switch(doc):
    """
    Analyzes a single tab switch document for suspicious activity.

    Args:
        doc (dict): The document fetched from MongoDB.

    Returns:
        dict: An analysis result containing suspicion score and reasons.
            {
                "document_id": str,
                "username": str,
                "problem_id": str,
                "timestamp": str,
                "suspicion_score": int,
                "reasons": list[str],
                "details": {
                    "from": {"url": str, "title": str},
                    "to": {"url": str, "title": str}
                }
            }
    """
    suspicion_score = 0
    reasons = []

    # Basic info extraction
    doc_id = str(doc.get("_id", {}))
    username = doc.get("username", "N/A")
    problem_id = doc.get("problemId", "N/A")
    problem_title = doc.get("problemTitle", "N/A")
    platform = doc.get("platform", "N/A").lower()
    timestamp_ms = doc.get("timestamp", {}).get("$date", {}).get("$numberLong")
    timestamp_iso = datetime.utcfromtimestamp(int(timestamp_ms) / 1000).isoformat() + "Z" if timestamp_ms else "N/A"


    from_url = doc.get("fromUrl", "")
    from_title = doc.get("fromTitle", "")
    to_url = doc.get("toUrl", "")
    to_title = doc.get("toTitle", "")

    # --- Analyze the Destination (toUrl, toTitle) ---
    to_domain = get_domain(to_url)
    to_text = f"{to_url} {to_title}".lower() # Combine URL and Title for keyword search

    if to_url == "external_application":
        suspicion_score += SCORE_WEIGHTS["TO_EXTERNAL_APPLICATION"]
        reasons.append(f"Switched to External Application (Intent unknown)")
    elif to_domain:
        # 1. Check for AI domains
        if to_domain in AI_DOMAINS:
            suspicion_score += SCORE_WEIGHTS["TO_AI"]
            reasons.append(f"Switched TO AI Domain: {to_domain}")
        # 2. Check for Solution domains
        elif to_domain in SOLUTION_DOMAINS:
            found_kw, matched_kw = contains_keywords(to_text, SUSPICIOUS_KEYWORDS)
            is_github_repo = to_domain == "github.com" and len(urlparse(to_url).path.split('/')) > 2 # Basic check for repo path
            is_leetcode_discuss = to_domain == "leetcode.com" and "/discuss/" in to_url.lower()
            is_different_problem = False
            # Check if navigating within the platform to a *different* problem or discussion
            if to_domain == f"{platform}.com": # e.g. leetcode.com
                 # Try to extract problem identifiers to compare
                 current_problem_norm = normalize_problem_identifier(problem_id) or normalize_problem_identifier(problem_title)
                 to_problem_norm_from_url = normalize_problem_identifier(to_url)
                 to_problem_norm_from_title = normalize_problem_identifier(to_title)

                 # Check if 'to' destination relates to a different problem
                 if current_problem_norm and \
                    ((to_problem_norm_from_url and to_problem_norm_from_url != current_problem_norm) or \
                     (to_problem_norm_from_title and to_problem_norm_from_title != current_problem_norm)):
                     # Avoid penalizing switches to general problem lists unless keywords suggest solutions
                     found_legit_kw, _ = contains_keywords(to_text, LEGITIMATE_PLATFORM_KEYWORDS)
                     if not found_legit_kw:
                         is_different_problem = True
                         suspicion_score += SCORE_WEIGHTS["WITHIN_PLATFORM_TO_DIFFERENT_PROBLEM"]
                         reasons.append(f"Switched TO different problem page/URL on {platform}: {to_title or to_url}")

                 if is_leetcode_discuss and not is_different_problem: # Don't double penalize
                     suspicion_score += SCORE_WEIGHTS["WITHIN_PLATFORM_TO_DISCUSSION"]
                     reasons.append(f"Switched TO {platform} discussion forum: {to_title or to_url}")

            # Apply scoring based on findings
            if is_leetcode_discuss:
                # Already scored above
                pass
            elif is_different_problem:
                 # Already scored above
                 pass
            elif is_github_repo:
                suspicion_score += SCORE_WEIGHTS["TO_GITHUB_REPO"]
                reasons.append(f"Switched TO GitHub repository: {to_url}")
                if found_kw:
                    suspicion_score += 1 # Bonus point if keywords also present
                    reasons.append(f"  (URL/Title also contains suspicious keyword: '{matched_kw}')")
            elif found_kw:
                suspicion_score += SCORE_WEIGHTS["TO_SOLUTION_DOMAIN_WITH_KEYWORDS"]
                reasons.append(f"Switched TO Solution Domain ({to_domain}) with keyword: '{matched_kw}'")
            elif to_domain != f"{platform}.com": # Avoid penalizing general navigation on the contest platform itself unless specified above
                 suspicion_score += SCORE_WEIGHTS["TO_SOLUTION_DOMAIN_GENERIC"]
                 reasons.append(f"Switched TO potential Solution Domain: {to_domain}")

        # 3. Check for Search Engines
        elif to_domain in SEARCH_DOMAINS:
            suspicion_score += SCORE_WEIGHTS["TO_SEARCH_ENGINE"]
            reasons.append(f"Switched TO Search Engine: {to_domain}")
            found_kw, matched_kw = contains_keywords(to_text, [problem_title] + SUSPICIOUS_KEYWORDS if problem_title else SUSPICIOUS_KEYWORDS)
            if found_kw:
                 suspicion_score += 1 # Bonus point
                 reasons.append(f"  (Search URL/Title contains relevant keyword: '{matched_kw}')")

        # 4. Check for suspicious keywords if domain wasn't flagged
        else:
            found_kw, matched_kw = contains_keywords(to_text, SUSPICIOUS_KEYWORDS)
            if found_kw:
                suspicion_score += SCORE_WEIGHTS["TO_SUSPICIOUS_KEYWORD_ONLY"]
                reasons.append(f"Switched TO URL/Title containing suspicious keyword: '{matched_kw}' in {to_domain or to_url}")

    # --- Analyze the Source (fromUrl) ---
    # Less weight, as it indicates where they *were*, not where they *went* during this event
    from_domain = get_domain(from_url)
    if from_domain:
        if from_domain in AI_DOMAINS:
            suspicion_score += SCORE_WEIGHTS["FROM_AI"]
            reasons.append(f"Switched FROM AI Domain: {from_domain}")
        elif from_domain in SOLUTION_DOMAINS:
            suspicion_score += SCORE_WEIGHTS["FROM_SOLUTION"]
            reasons.append(f"Switched FROM potential Solution Domain: {from_domain}")
            # Could add keyword check here too if desired

    # --- Final Score Adjustment ---
    # Cap the score at the defined maximum
    final_score = min(suspicion_score, MAX_SCORE)

    # If score is 0, add a neutral reason
    if final_score == 0 and not reasons:
        reasons.append("No suspicious activity detected in this switch.")
    elif final_score > 0 and not reasons:
         # Should not happen if scoring logic is correct, but as a fallback
         reasons.append("Suspicious activity detected based on scoring rules.")


    return {
        "document_id": doc_id,
        "username": username,
        "problem_id": problem_id,
        "platform": platform,
        "timestamp": timestamp_iso,
        "suspicion_score": final_score,
        "reasons": reasons,
        "details": {
            "from": {"url": from_url, "title": from_title},
            "to": {"url": to_url, "title": to_title}
        }
    }


# --- MongoDB Connection and Main Execution ---
# WARNING: Avoid hardcoding credentials in production code. Use environment variables or a config file.
MONGO_URI = "mongodb+srv://admin:7vNJvFHGPVvbWBRD@syntaxsentry.rddho.mongodb.net/?retryWrites=true&w=majority&appName=syntaxsentry"
DATABASE_NAME = "test"
COLLECTION_NAME = "activities"

# Keep your original fetch function
def fetch_document_by_id(document_id):
    """Fetches a single document from MongoDB by its _id."""
    try:
        # It's better practice to create the client inside the function
        # or manage it globally if the script runs continuously.
        # For a single run script, creating it here is okay.
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]

        # Validate ObjectId
        try:
            obj_id = ObjectId(document_id)
        except Exception as e:
            logging.error(f"Invalid ObjectId format: {document_id} - {e}")
            client.close()
            return None, f"Invalid ObjectId format: {document_id}"

        logging.info(f"Attempting to fetch document with _id: {obj_id}")
        document = collection.find_one({"_id": obj_id})
        client.close() # Close connection after fetching

        if document:
            logging.info(f"Document found.")
            return document, None
        else:
            logging.warning(f"No document found with _id: {document_id}")
            return None, f"No document found with _id: {document_id}"
    except Exception as e:
        logging.error(f"Database connection or query failed: {e}")
        # Ensure client is closed if created and an error occurs
        try:
            if 'client' in locals() and client:
                client.close()
        except Exception as close_err:
            logging.error(f"Error closing MongoDB connection during error handling: {close_err}")
        return None, f"Database error: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing object_id argument"}, indent=2))
        sys.exit(1)

    document_id = sys.argv[1]
    logging.info(f"Received request to analyze document ID: {document_id}")

    doc_content, error = fetch_document_by_id(document_id)

    if error:
        print(json.dumps({"error": error}, indent=2))
        sys.exit(1)

    if doc_content:
        if doc_content.get("eventType") != "tab_switch":
             print(json.dumps({"error": f"Document {document_id} is not a 'tab_switch' event"}, indent=2))
             sys.exit(1)

        analysis_result = analyze_tab_switch(doc_content)
        print(json.dumps(analysis_result, indent=2))
    else:
        # Error message already printed by fetch_document_by_id in case of no doc found
        # This case should theoretically be covered by the error check above
         print(json.dumps({"error": f"Failed to retrieve document {document_id}"}, indent=2))
         sys.exit(1) # Should exit in fetch_document_by_id failure case already