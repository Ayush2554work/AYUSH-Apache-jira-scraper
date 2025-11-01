import requests
import json
import time
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# This is the Apache Jira API endpoint
JIRA_API_URL = "https://issues.apache.org/jira/rest/api/2/search"

# File to store our progress
STATE_FILE = "scraper_state.json"

class JiraScraper:
    """
    A fault-tolerant, resumable scraper for Apache Jira.
    
    Handles:
    - API Pagination (using 'startAt')
    - Resumability (using 'scraper_state.json')
    - Network Errors (5xx, timeouts) via exponential backoff
    - Rate Limits (429) via specific sleep handling
    """
    
    def __init__(self, projects):
        self.projects = projects
        self.session = requests.Session()
        self.state = self._load_state()

    def _load_state(self):
        """Loads the last saved state from the state file."""
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logging.warning("No valid state file found. Starting from scratch.")
            return {}

    def _save_state(self):
        """Saves the current state to the state file."""
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)),
        reraise=True
    )
    def _fetch_page(self, project_key, start_at, max_results=50):
        """
        Fetches a single page of issues with automatic retries for
        network errors and 5xx server issues.
        """
        params = {
            'jql': f'project = "{project_key}" ORDER BY created ASC',
            'startAt': start_at,
            'maxResults': max_results,
            # We explicitly ask for fields to be efficient
            'fields': 'summary,description,status,priority,reporter,assignee,labels,created,updated,comment'
        }
        
        logging.info(f"Fetching {project_key}: startAt={start_at}, maxResults={max_results}")
        
        try:
            response = self.session.get(JIRA_API_URL, params=params, timeout=30)
            
            # Handle specific HTTP error codes
            if response.status_code == 429:
                logging.warning("Rate limit (429) hit. Sleeping for 60 seconds...")
                time.sleep(60)
                # We return None to signal the outer loop to retry this *same* request
                return None
            
            # Handle other client/server errors
            response.raise_for_status() 
            
            return response.json()

        except requests.exceptions.HTTPError as e:
            if 500 <= e.response.status_code < 600:
                logging.error(f"Server error (5xx) encountered: {e}. Tenacity will retry.")
                raise  # Reraise to trigger tenacity
            else:
                logging.error(f"HTTP Error: {e}. Skipping this request.")
                return {'issues': [], 'total': 0} # Return empty to skip
        except requests.exceptions.RequestException as e:
            logging.error(f"Request Exception: {e}. Tenacity will retry.")
            raise # Reraise to trigger tenacity


    def scrape(self):
        """
        Main generator to scrape all issues for the configured projects.
        It yields one issue at a time.
        """
        for project in self.projects:
            if project not in self.state:
                self.state[project] = {"start_at": 0, "completed": False}
            
            if self.state[project].get("completed", False):
                logging.info(f"Project {project} already marked as completed. Skipping.")
                continue

            start_at = self.state[project]["start_at"]
            
            while True:
                data = self._fetch_page(project, start_at)

                if data is None:
                    # This means we hit a 429 and should retry the *same* page
                    continue 

                if 'issues' not in data or not data['issues']:
                    # No more issues left
                    logging.info(f"No more issues found for {project}.")
                    self.state[project]["completed"] = True
                    self._save_state()
                    break

                issues = data['issues']
                total = data.get('total', 0)
                
                for issue in issues:
                    yield issue
                
                # Update progress
                start_at += len(issues)
                self.state[project]["start_at"] = start_at
                self._save_state()
                
                logging.info(f"Progress {project}: {start_at} / {total}")
                
                if start_at >= total:
                    logging.info(f"Successfully completed scraping for {project}.")
                    self.state[project]["completed"] = True
                    self._save_state()
                    break