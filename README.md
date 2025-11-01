# AYUSH'S JIRA SCRAPER😎

This project is a data scraping and transformation pipeline developed for a tutor assignment. It extracts public issue data from Apache’s Jira instance and converts it into a structured JSONL format, suitable for training Large Language Models (LLMs).

**Author:** Ayush Kumar
**Repo:** `https://github.com/Ayush2554work/AYUSH-Apache-jira-scraper`

---

## Architecture Overview

The system is a Python-based pipeline composed of three main modules:

1.  **`scraper.py` (The Scraper)**: A class-based scraper responsible for fetching data from the public Jira REST API. It is designed to be fault-tolerant and resumable.
2.  **`transformer.py` (The Transformer)**: A set of functions that take raw API JSON as input and transform it into a clean, structured JSONL format.
3.  **`main.py` (The Orchestrator)**: The main entry point that initializes the scraper, iterates through issues, passes them to the transformer, and appends the results to an output file.

Data flows from the `scraper` (one issue at a time) to the `transformer`, and then into the final `jira_corpus.jsonl` file.

---

## Setup and Execution

### 1. Prerequisites
* Python 3.8+
* `git`

### 2. Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Ayush2554work/AYUSH-Apache-jira-scraper.git](https://github.com/Ayush2554work/AYUSH-Apache-jira-scraper.git)
    cd AYUSH-Apache-jira-scraper
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create the initial state file:**
    ```bash
    touch scraper_state.json
    echo "{}" > scraper_state.json
    ```

### 3. How to Run

Simply execute the `main.py` script:

```bash
python main.py
```

The script will start fetching data for the projects defined in `main.py` (default: `SPARK`, `KAFKA`, `HADOOP`). It will print progress to the console and write data to `jira_corpus.jsonl`.

---

## Design Reasoning and Edge Cases Handled

This section details the design decisions made to meet the assignment's requirements for a robust, fault-tolerant, and efficient system.

### 1. Choice of API over HTML Scraping

* **Rationale**: The assignment hinted at solutions beyond HTML scraping. I chose to use the official **Jira REST API**.
* **Advantage**: This is far more stable, faster, and reliable than parsing HTML. It provides structured JSON, eliminating the need for brittle selectors and handling data exactly as the system stores it.

### 2. Fault Tolerance and Resumability

This is the most critical feature of the pipeline.

* **Problem**: The script could fail due to network errors, API limits, or a server crash. Scraping can take hours, and progress should not be lost.
* **Solution**:
    1.  **Stateful Scraper**: The `scraper.py` class uses a `scraper_state.json` file. It saves its progress (the `startAt` index) for **each project** after every successfully fetched page.
    2.  **Resumability**: On startup, the scraper reads this state file. If it finds a `startAt` index for a project, it resumes from that exact point, not from the beginning.
    3.  **Append-Only Output**: The `main.py` script opens the `jira_corpus.jsonl` file in **append (`'a'`) mode**. This ensures that even if the script crashes, previously scraped and transformed data is preserved.

### 3. Handling Network and Data Edge Cases

* **HTTP 5xx (Server Errors) & Timeouts**:
    * **Solution**: I used the `tenacity` library. The `_fetch_page` method is decorated with `@retry`, which automatically retries on `RequestException` (like timeouts) and server-side errors (500, 502, 503) using **exponential backoff**. This prevents overwhelming the server and gracefully handles temporary outages.

* **HTTP 429 (Rate Limits)**:
    * **Solution**: This error requires a specific response. The scraper explicitly checks for `response.status_code == 429`, logs a warning, and executes a `time.sleep(60)` (60 seconds) before retrying the *exact same page*.

* **Empty or Malformed Data**:
    * **Solution**: The `transformer.py` module is wrapped in a `try...except` block. If a single issue is missing critical fields (e.g., `fields` is `null` or a comment is malformed), the exception is logged, that one issue is skipped, and the pipeline continues. **This prevents one bad issue from crashing the entire job.**

### 4. Optimization Decisions

* **Efficient API Calls**: Instead of fetching all 100+ fields for an issue, the `fields` parameter in the API call explicitly requests *only* the data we need (summary, description, comment, status, etc.). This reduces payload size and speeds up API response times.
* **Generator-Based Processing**: The `scraper.scrape()` method is a **generator** (it uses `yield`). It does not load all 100,000+ issues into memory. It fetches one page, yields its issues one-by-one, and they are immediately transformed and written to disk. This gives the pipeline a very small memory footprint, allowing it to run on any machine.
* **Connection Pooling**: By using `requests.Session()`, we reuse the underlying TCP connection for multiple requests to the same host, which is more efficient than opening a new connection for every call.

---

## Future Improvements

* **Asynchronous Scraping**: Use `asyncio` and `httpx` to scrape multiple projects (or even multiple pages within a project) concurrently, which would dramatically speed up the total runtime.
* **Advanced Text Cleaning**: The `clean_text` function is very basic. A future version should use regex or a proper library to parse Jira's wiki markup (`[links]`, `*bold*`, tables, etc.) into clean markdown or text.
* **Containerization**: The entire application could be packaged into a Docker container for easy deployment and reproducible builds.
* **Better Derived Tasks**: The derived tasks are simple examples. More complex Q&A pairs, code-generation tasks (from code blocks), and intent classification could be generated.