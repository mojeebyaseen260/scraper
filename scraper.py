"""
Jeddah Cold Storage Scraper - Optimized
- 8 parallel Chrome drivers
- ThreadPoolExecutor for async email fetching
- Auto-save every 30 new results
- Resume support, retry failed queries
- Output: name + email only
"""

import os
import re
import sys
import json
import time
import socket
import threading
import requests
import pandas as pd
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===== SETTINGS =====
NUM_DRIVERS     = 8
AUTO_SAVE_EVERY = 30
DRIVER_TIMEOUT  = 20
PAGE_WAIT       = 0.8
NET_RETRY_WAIT  = 10
MAX_PLACES_PER_QUERY = 20
EMAIL_TIMEOUT   = 8   # seconds per website request
EMAIL_WORKERS   = 16  # parallel email fetchers

AREAS = [
    "Al Balad Jeddah", "Al Hamra Jeddah", "Al Rawdah Jeddah",
    "Al Andalus Jeddah", "Al Naeem Jeddah", "Al Khalidiyah Jeddah",
    "Industrial Area Jeddah", "Al Khumra Jeddah", "Al Harazat Jeddah",
    "Al Rehab Jeddah", "Al Aziziyah Jeddah", "Al Safa Jeddah",
    "Al Marwah Jeddah", "Al Shati Jeddah", "Al Zahraa Jeddah",
    "Al Faisaliyah Jeddah", "Al Bawadi Jeddah", "Al Wurud Jeddah",
    "Al Nuzha Jeddah", "Al Muhammadiyah Jeddah", "Al Salamah Jeddah",
    "Al Rabwah Jeddah", "Al Rowais Jeddah", "Al Mishrifah Jeddah",
    "Al Waziriyah Jeddah", "Al Bughdadiyah Jeddah", "Al Hindawiyah Jeddah",
    "Al Jamiah Jeddah", "Al Thaghr Jeddah", "Al Mahjar Jeddah",
]

KEYWORDS = [
    # English
    "cold storage", "freezer room", "cold room", "refrigerated warehouse",
    "cold store", "freezer storage", "chiller room", "blast freezer",
    "frozen storage", "cold chain", "refrigerated storage", "ice storage",
    "cold storage facility", "cold storage center", "cold storage depot",
    "cold storage unit", "cold storage company", "cold storage warehouse",
    "cold storage plant", "cold storage building",
    "food cold storage", "meat cold storage", "fish cold storage",
    "vegetable cold storage", "fruit cold storage", "dairy cold storage",
    "seafood cold storage", "poultry cold storage", "egg cold storage",
    "frozen meat storage", "frozen fish storage", "frozen food storage",
    "frozen seafood storage", "frozen poultry storage", "frozen dairy storage",
    "frozen vegetable storage", "frozen fruit storage", "beef cold storage",
    "chicken cold storage", "lamb cold storage",
    "pharmaceutical cold storage", "industrial cold storage",
    "commercial freezer", "walk in freezer", "walk in cooler",
    "frozen food warehouse", "refrigeration plant", "cold logistics",
    "temperature controlled warehouse", "freezer warehouse",
    "refrigerated distribution", "freezer facility", "chill store",
    "refrigeration warehouse", "cold chain warehouse", "cold chain facility",
    "controlled temperature storage", "sub zero storage", "deep freeze storage",
    "blast freeze room", "quick freeze room",
    "cold storage Jeddah", "freezer room Jeddah", "cold room Jeddah",
    "refrigerated warehouse Jeddah", "cold store Jeddah",
    "freezer storage Jeddah", "chiller room Jeddah", "cold chain Jeddah",
    "frozen storage Jeddah", "cold storage Saudi Arabia",
    "ice plant Jeddah", "cold storage rental", "freezer rental Jeddah",
    "cold room rental", "refrigerated container", "reefer storage",
    "cold storage logistics", "food grade cold storage", "halal cold storage",
    "cold storage import export", "port cold storage Jeddah",
    "cold storage near port", "industrial freezer Jeddah",
    "commercial cold storage Jeddah", "food warehouse Jeddah",
    "frozen food company Jeddah", "refrigeration company Jeddah",
    "cold storage services Jeddah", "freezer room services",
    "cold storage solutions Jeddah",
    "cold storage near me Jeddah", "best cold storage Jeddah",
    "cold storage for rent Jeddah", "cold storage for lease Jeddah",
    "cold storage operator Jeddah", "cold storage provider Jeddah",
    "cold storage distributor Jeddah", "cold storage supplier Jeddah",
    "cold storage contractor Jeddah", "cold storage manager Jeddah",
    # Arabic
    "مستودع تبريد", "غرفة تبريد", "ثلاجة تخزين", "مخزن مبرد",
    "تخزين مبرد", "مستودع مجمد", "غرفة تجميد", "ثلاجة صناعية",
    "مخزن تبريد جدة", "مستودعات تبريد",
    "ثلاجة لحوم", "ثلاجة اسماك", "مستودع غذائي مبرد",
    "مستودع دواجن مبرد", "ثلاجة فواكه", "مخزن مأكولات بحرية",
    "مستودع خضروات مبرد", "ثلاجة منتجات البحر", "مخزن لحوم مجمدة",
    "ثلاجة دجاج", "مستودع بيض مبرد", "ثلاجة منتجات الألبان",
    "مخزن خضروات مبردة", "ثلاجة فواكه مجمدة", "مستودع اسماك مجمدة",
    "تبريد صناعي", "مخازن مبردة", "تخزين مجمد",
    "ثلاجة تجارية", "مخزن مجمدات", "تبريد وتجميد",
    "شركة تبريد", "مستودع الباردة", "ثلاجة مركزية",
    "مستودع تجميد", "تبريد جدة", "مخزن مبرد جدة",
    "تخزين بارد جدة", "مستودعات مبردة جدة", "غرف تبريد جدة",
    "ثلاجات صناعية جدة", "مخازن تبريد جدة", "شركة تبريد جدة",
    "مستودع مبرد جدة", "تجميد صناعي جدة",
    "سلسلة التبريد جدة", "نقل مبرد جدة", "لوجستيات التبريد",
    "مستودع درجة حرارة متحكم بها", "تخزين صفر درجة",
    "تجميد سريع", "غرفة تجميد سريع", "مستودع تبريد للإيجار",
    "ثلاجة للإيجار جدة", "مستودع مبرد للإيجار",
    "ثلاجة ميناء جدة", "مستودع مبرد ميناء", "تخزين مبرد ميناء جدة",
    "مستودع استيراد مبرد", "ثلاجة تصدير جدة",
    "مستودع حلال مبرد", "تخزين حلال جدة", "ثلاجة حلال",
    "مستودع صيدلاني مبرد", "تخزين أدوية مبرد جدة",
    "ثلاجة صيدلانية", "مخزن أدوية مبرد", "تبريد صيدلاني جدة",
    "مستودع تبريد تجاري", "ثلاجة مركزية جدة", "مخزن تجميد جدة",
    "مستودعات مجمدات جدة", "خدمات تبريد جدة",
    "ايجار مستودع مبرد", "ايجار غرفة تبريد جدة",
    "مورد تبريد جدة", "مقاول تبريد جدة",
]

# ===== Shared state =====
results_lock      = threading.Lock()
save_lock         = threading.Lock()
progress_lock     = threading.Lock()
all_data          = {}
seen_websites     = set()
save_counter      = [0]
completed_queries = set()
failed_queries    = []

# Compiled regex for performance
_EMAIL_RE   = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_JUNK_RE    = re.compile(r"\.(png|jpg|jpeg|gif|svg|webp|woff|css|js)$", re.I)
_JUNK_HOSTS = {"sentry", "example", "domain", "schema", "w3.org", "googleapis"}

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
})

os.makedirs("output", exist_ok=True)
PROGRESS_FILE = "output/progress.json"
DATA_FILE_CSV = "output/jeddah_cold_storage_all.csv"


# ===== Internet check =====
def is_connected():
    try:
        socket.setdefaulttimeout(5)
        socket.create_connection(("8.8.8.8", 53))
        return True
    except OSError:
        return False


def wait_for_internet(worker_id):
    if not is_connected():
        print(f"\n  [Worker-{worker_id}] Internet down. Waiting...")
        while not is_connected():
            time.sleep(NET_RETRY_WAIT)
        print(f"  [Worker-{worker_id}] Internet restored.")


# ===== Progress =====
def load_progress():
    global all_data, completed_queries
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            completed_queries = set(json.load(f))
        print(f"  Previous progress: {len(completed_queries)} queries done")

    if os.path.exists(DATA_FILE_CSV):
        try:
            df = pd.read_csv(DATA_FILE_CSV, encoding="utf-8-sig")
            for _, row in df.iterrows():
                key = f"{row.get('name','')}|{row.get('email','')}"
                if key.strip("|"):
                    all_data[key] = {"name": row.get("name",""), "email": row.get("email","")}
            print(f"  Previous data loaded: {len(all_data)} places")
        except Exception as e:
            print(f"  Data load error: {e}")


def mark_done(query):
    with progress_lock:
        completed_queries.add(query)
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(completed_queries), f, ensure_ascii=False)


def clear_progress():
    global all_data, completed_queries, failed_queries, seen_websites
    all_data = {}
    completed_queries = set()
    seen_websites = set()
    failed_queries = []
    for fp in [
        PROGRESS_FILE, DATA_FILE_CSV,
        "output/jeddah_cold_storage_all.xlsx",
    ]:
        if os.path.exists(fp):
            os.remove(fp)
    print("  Old data cleared. Starting fresh...")


# ===== Auto save =====
def auto_save(final=False):
    with save_lock:
        rows = list(all_data.values())
        if not rows:
            return
        df = pd.DataFrame(rows, columns=["name", "email"])
        df.to_csv(DATA_FILE_CSV, index=False, encoding="utf-8-sig")
        if final:
            df.to_excel("output/jeddah_cold_storage_all.xlsx", index=False)
        if not final:
            print(f"\n  [AUTO-SAVE] {len(rows)} places\n")


# ===== Email extraction =====
def extract_email_from_website(url):
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url

    # Deduplicate: same website already fetched
    with results_lock:
        if url in seen_websites:
            return ""
        seen_websites.add(url)

    try:
        resp = _SESSION.get(url, timeout=EMAIL_TIMEOUT, allow_redirects=True)
        emails = _EMAIL_RE.findall(resp.text)
        seen, result = set(), []
        for e in emails:
            el = e.lower()
            host = el.split("@")[-1]
            if (
                el not in seen
                and not _JUNK_RE.search(e)
                and not any(j in host for j in _JUNK_HOSTS)
            ):
                seen.add(el)
                result.append(e)
                if len(result) == 3:
                    break
        return ", ".join(result)
    except Exception:
        return ""


# ===== Driver setup =====
def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=ar")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(DRIVER_TIMEOUT)
    return driver


# ===== Extract place info (no email here — done in batch later) =====
def extract_place_info(driver, keyword, area):
    try:
        def _get(css):
            try:
                return driver.find_element(By.CSS_SELECTOR, css).text.strip()
            except Exception:
                return ""

        info = {
            "name":    _get("h1.DUwDvf"),
            "website": _get("a[data-item-id='authority'] .Io6YTe"),
            "email":   "",
        }
        return info if info["name"] else None
    except Exception:
        return None


# ===== Add result =====
def add_result(info):
    key = f"{info.get('name','')}|{info.get('email','')}"
    if not key.strip("|"):
        return
    with results_lock:
        if key not in all_data:
            all_data[key] = {"name": info.get("name",""), "email": info.get("email","")}
            save_counter[0] += 1
            if save_counter[0] >= AUTO_SAVE_EVERY:
                save_counter[0] = 0
                threading.Thread(target=auto_save, daemon=True).start()


# ===== Scrape one query =====
def scrape_query(driver_box, query, keyword, area, worker_id, email_executor):
    place_urls = []

    for attempt in range(2):
        wait_for_internet(worker_id)
        try:
            driver = driver_box[0]
            url = (
                "https://www.google.com/maps/search/"
                + query.replace(" ", "+")
                + "+Jeddah+Saudi+Arabia"
            )
            driver.get(url)
            time.sleep(PAGE_WAIT)

            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[role='feed']"))
                )
            except Exception:
                pass

            # Scroll to load more results
            for _ in range(5):
                try:
                    feed = driver.find_element(By.CSS_SELECTOR, "[role='feed']")
                    driver.execute_script(
                        "arguments[0].scrollTop = arguments[0].scrollHeight", feed
                    )
                    time.sleep(1.2)
                except Exception:
                    break

            cards = driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")
            place_urls = list({
                c.get_attribute("href")
                for c in cards
                if c.get_attribute("href")
            })
            break

        except Exception as e:
            print(f"  [Worker-{worker_id}] Driver stuck ({e.__class__.__name__}), restarting...")
            try:
                driver_box[0].quit()
            except Exception:
                pass
            time.sleep(2)
            try:
                driver_box[0] = setup_driver()
            except Exception as re_err:
                print(f"  [Worker-{worker_id}] Restart failed: {re_err}")
                with progress_lock:
                    failed_queries.append(query)
                return

    # Collect place info, submit email fetches to thread pool
    futures = []
    for purl in place_urls[:MAX_PLACES_PER_QUERY]:
        for attempt in range(2):
            wait_for_internet(worker_id)
            try:
                driver = driver_box[0]
                driver.get(purl)
                time.sleep(PAGE_WAIT)
                info = extract_place_info(driver, keyword, area)
                if info:
                    add_result(info)
                    # Submit email fetch asynchronously if website exists
                    if info.get("website"):
                        key = f"{info['name']}|{info['email']}"
                        fut = email_executor.submit(extract_email_from_website, info["website"])
                        futures.append((fut, key))
                break
            except Exception as e:
                print(f"  [Worker-{worker_id}] Place error ({e.__class__.__name__}), restarting driver...")
                try:
                    driver_box[0].quit()
                except Exception:
                    pass
                time.sleep(2)
                try:
                    driver_box[0] = setup_driver()
                except Exception:
                    break

    # Collect email results and update records
    for fut, key in futures:
        try:
            email = fut.result(timeout=EMAIL_TIMEOUT + 2)
            if email:
                with results_lock:
                    if key in all_data:
                        all_data[key]["email"] = email
        except Exception:
            pass


# ===== Worker thread =====
def worker(worker_id, task_queue, email_executor):
    print(f"[Worker-{worker_id}] Starting...")
    try:
        driver_box = [setup_driver()]
    except Exception as e:
        print(f"[Worker-{worker_id}] Failed to create driver: {e}")
        return

    while True:
        try:
            item = task_queue.get(timeout=5)
        except Empty:
            break

        query, keyword, area = item
        try:
            print(f"[Worker-{worker_id}] Searching: {query}")
            scrape_query(driver_box, query, keyword, area, worker_id, email_executor)
            mark_done(query)
        except Exception as e:
            print(f"[Worker-{worker_id}] Error: {e}")
            with progress_lock:
                failed_queries.append(query)
        finally:
            task_queue.task_done()

    try:
        driver_box[0].quit()
    except Exception:
        pass
    print(f"[Worker-{worker_id}] Done")


# ===== MAIN =====
def main():
    print("=" * 60)
    print("Jeddah Cold Storage Scraper")
    print(f"Workers: {NUM_DRIVERS} | Email threads: {EMAIL_WORKERS} | Auto-save: {AUTO_SAVE_EVERY}")
    print("=" * 60)

    if os.path.exists(PROGRESS_FILE):
        print("\nPrevious progress found!")
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            done_count = len(json.load(f))
        total_all = len(AREAS) * len(KEYWORDS)
        print(f"  Completed : {done_count} / {total_all}")
        print(f"  Remaining : {total_all - done_count}\n")
        # auto-resume if --resume flag, fresh if --fresh, else ask
        if "--resume" in sys.argv:
            choice = "y"
        elif "--fresh" in sys.argv:
            choice = "n"
        else:
            choice = input("Resume? (y = Yes / n = Fresh start): ").strip().lower()
        if choice == "y":
            load_progress()
            print("  Resuming...\n")
        else:
            clear_progress()
    else:
        print("  First run. Starting fresh...\n")

    task_queue = Queue()
    for area in AREAS:
        for keyword in KEYWORDS:
            q = f"{keyword} {area}"
            if q not in completed_queries:
                task_queue.put((q, keyword, area))

    total_tasks = task_queue.qsize()
    print(f"Total tasks: {total_tasks}\n")

    with ThreadPoolExecutor(max_workers=EMAIL_WORKERS) as email_executor:
        threads = []
        for i in range(NUM_DRIVERS):
            t = threading.Thread(
                target=worker,
                args=(i + 1, task_queue, email_executor),
                daemon=True,
            )
            t.start()
            threads.append(t)
            time.sleep(1)

        while any(t.is_alive() for t in threads):
            done = total_tasks - task_queue.qsize()
            with results_lock:
                found   = len(all_data)
                with_em = sum(1 for r in all_data.values() if r.get("email"))
            print(
                f"\r  Progress: {done}/{total_tasks} | "
                f"Places: {found} | With email: {with_em} | "
                f"Failed: {len(failed_queries)}",
                end="", flush=True,
            )
            time.sleep(3)

        for t in threads:
            t.join()

    # Retry failed queries
    if failed_queries:
        print(f"\n\nRetrying {len(failed_queries)} failed queries...")
        retry_queue = Queue()
        for q in failed_queries:
            for area in AREAS:
                if area in q:
                    kw = q.replace(f" {area}", "").strip()
                    retry_queue.put((q, kw, area))
                    break
        failed_queries.clear()

        with ThreadPoolExecutor(max_workers=EMAIL_WORKERS) as email_executor:
            retry_threads = []
            for i in range(min(NUM_DRIVERS, retry_queue.qsize())):
                t = threading.Thread(
                    target=worker,
                    args=(i + 1, retry_queue, email_executor),
                    daemon=True,
                )
                t.start()
                retry_threads.append(t)
            for t in retry_threads:
                t.join()
        print(f"  Retry done. Still failed: {len(failed_queries)}")

    # Final save (includes Excel)
    print("\n\nFinal save...")
    auto_save(final=True)

    with results_lock:
        total   = len(all_data)
        with_em = sum(1 for r in all_data.values() if r.get("email"))

    print("\n" + "=" * 60)
    print("Done!")
    print(f"  Total places  : {total}")
    print(f"  With email    : {with_em}")
    print(f"  Failed queries: {len(failed_queries)}")
    print("  Output: output/")
    print("=" * 60)


if __name__ == "__main__":
    main()
