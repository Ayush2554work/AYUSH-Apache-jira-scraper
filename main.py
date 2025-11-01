import json
import logging
from scraper import JiraScraper
from transformer import transform_to_jsonl

# --- Configuration ---
# You are required to pick 3 projects.
# Here are 3 popular ones. You can change them.
APACHE_PROJECTS = ["SPARK", "KAFKA", "HADOOP"]

# This is our final output file.
OUTPUT_JSONL_FILE = "jira_corpus.jsonl"

# --- Main Execution ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logging.info(f"Starting Apache Jira Scraper for Ayush...")
    
    # 1. Initialize the scraper
    scraper = JiraScraper(projects=APACHE_PROJECTS)
    
    # We open the file in 'a' (append) mode.
    # This makes our pipeline fault-tolerant. If it crashes,
    # we don't lose the data we already wrote.
    try:
        with open(OUTPUT_JSONL_FILE, 'a', encoding='utf-8') as f:
            
            # 2. Scrape and yield one issue at a time
            for issue_data in scraper.scrape():
                
                # 3. Transform the issue
                transformed_data = transform_to_jsonl(issue_data)
                
                # 4. Write to JSONL file
                if transformed_data:
                    json_line = json.dumps(transformed_data)
                    f.write(json_line + '\n')

        logging.info(f"Scraping complete. Data saved to {OUTPUT_JSONL_FILE}")

    except Exception as e:
        logging.critical(f"A fatal error occurred: {e}")
        logging.critical("Scraper stopped. Rerun the script to resume from the last saved state.")