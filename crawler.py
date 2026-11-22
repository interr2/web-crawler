import urllib.request
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.parse import urldefrag
import re
import queue
import threading
import time
import html
import argparse
from concurrent.futures import ThreadPoolExecutor

def log(message): # For verbose mode
    if verboseMode:
        print(message)

def filterLinks(linkList, url):
    filteredLinkList = []

    for link in linkList:
        link = html.unescape(link).replace('"', "").replace("'", "").strip().rstrip(".,;)&")

        if not link or link.lower().startswith(("#", "mailto:", "javascript:", "tel:")):
            continue

        link = urldefrag(urljoin(url, link))[0]
        parsed = urlparse(link)

        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            continue

        filteredLinkList.append(link)

    return filteredLinkList

def isCrawlable(link):
    parsed = urlparse(link)

    if crawlerMode == 2:
        return True

    if crawlerMode == 3 and parsed.netloc.removeprefix("www.") != startDomain:
        return False

    if parsed.netloc in junkDomains or any(j in link for j in junkParts): # Nice greek language
        return False

    lastSegment = parsed.path.rsplit("/", 1)[-1]
    if "." in lastSegment and not lastSegment.lower().endswith(extensions):
        return False

    return True

def findDifferentLinks(list):
    diffLinks = []

    for i in list:
        key = i.replace("://www.", "://", 1).rstrip("/")
        if key in visited:
            continue
        visited.add(key)
        diffLinks.append(i)

    return diffLinks

def writeFinalLinks(file, list):
    with open(file, "a", encoding="utf-8") as linkFile:
        for i in list:
            linkFile.write(i + "\n")

def getLinks(url, file):
    global linkN, errorN

    log(f"[getLinks] Crawling: {url}")
    time.sleep(sleepTime)

    source = ""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            contentType = response.headers.get("Content-Type", "").lower()
            isHtml = "text/html" in contentType or "application/xhtml" in contentType

            if not isHtml:
                if crawlerMode != 2:
                    return
                if not any(t in contentType for t in readableTypes):
                    return

            source = response.read(maxReadSize).decode("utf-8", errors="ignore")
    except Exception as e:
        log(f"[ERROR] Request failed ({url}): {e}")
        with stateLock:
            with open(errorFile, "a", encoding="utf-8") as errors:
                errors.write(f"[ERROR] {url}: {e} \n")
            if statsMode:
                errorN += 1
        return

    if crawlerMode == 2:
        if keyWord.lower() in html.unescape(source).lower():
            with stateLock:
                writeFinalLinks(file, [url])

    if not isHtml:
        return

    hrefLinks = re.findall(r'href=["\'](.*?)["\']', source, re.IGNORECASE)
    httpsLinks = re.findall(r'https:\/\/[^\s"\'<>\\]+', source)
    finalList = hrefLinks + httpsLinks

    finalList = filterLinks(finalList, url)
    finalList = list(dict.fromkeys(finalList))

    with stateLock:
        finalList = findDifferentLinks(finalList)
        if crawlerMode == 1:
            keyWordLinks = []
            for link in finalList:
                if keyWord.lower() in link.lower():
                    keyWordLinks.append(link)

            writeFinalLinks(file, keyWordLinks)

        crawlList = []
        for l in finalList:
            if isCrawlable(l):
                crawlList.append(l)

        if crawlerMode == 0 or crawlerMode == 3:
            writeFinalLinks(file, crawlList)

        if statsMode:
            linkN += len(finalList)

    log(f"[getLinks] {len(finalList)} new links found in {url}")

    for newUrl in crawlList:
        registerUrl(newUrl)

def registerUrl(url):
    global maxThreadN, maxThreadT

    if stopEvent.is_set():
        return

    domain = urlparse(url).netloc.removeprefix("www.")
    if not domain:
        return
    
    if crawlerMode == 3: 
        threadLimit = mode3ThreadN
    else:
        threadLimit = 1

    with stateLock:
        if domain not in domainQueues:
            domainQueues[domain] = queue.Queue()
            log(f"[registerUrl] Queue created: {domain}")
        domainQueues[domain].put(url)

        if activeDomains.get(domain, 0) < threadLimit:
            activeDomains[domain] = activeDomains.get(domain, 0) + 1
            log(f"[registerUrl] Starting new thread for domain: {domain}")
            executor.submit(domainWorker, domain)

            if statsMode:
                currenThreadN = min(sum(activeDomains.values()), maxThread)
                if currenThreadN > maxThreadN:
                    maxThreadN = currenThreadN
                    maxThreadT = time.time() - startTime

def domainWorker(domain):
    targetQueue = domainQueues[domain]
    log(f"[domainWorker] Thread started: {domain}")

    while not stopEvent.is_set():
        try:
            currentUrl = targetQueue.get(timeout=3)
        except queue.Empty:
            with stateLock: # Check again with stateLock
                if targetQueue.empty():
                    activeDomains[domain] -= 1
                    if activeDomains[domain] == 0:
                        del activeDomains[domain]
                    log(f"[domainWorker] Queue empty, closing thread: {domain}")
                    return
            continue

        try:
            getLinks(currentUrl, file)
        except Exception as e:
            log(f"[ERROR] domainWorker error: {currentUrl}: {e}")
        finally:
            targetQueue.task_done()

# Only the common ones
junkDomains = ("fonts.googleapis.com", "fonts.gstatic.com", "googletagmanager.com", "s.w.org",
               "api.w.org", "i0.wp.com", "gmpg.org")
junkParts = ("/feed", "/wp-json", "?onsale=", "?replytocom", "/xmlrpc", "?orderby=", "?add-to-cart")
extensions = (".html", ".php", ".htm", ".asp", ".aspx", ".jsp")
readableTypes = ("text/", "json", "xml")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web crawler")

    parser.add_argument("url", help="Start url")
    parser.add_argument("--mode", type=int, default=0, choices=[0, 1, 2, 3],
                        help="0: Default mode, 1: Searchs keyword in url, 2: Searchs keyword in content, " \
                        "3: Crawl only given site")
    parser.add_argument("--keyword", default="", help="Keyword to search for (modes 1 and 2)")
    parser.add_argument("--thread", type=int, default=100, help="Max thread number")
    parser.add_argument("--mode3-thread", type=int, default=5, help="Thread number for mode 3")
    parser.add_argument("--sleep", type=float, default=0.5, help="Delay between requests")
    parser.add_argument("--max-time", type=int, default=10, help="Max run time (0 = unlimited)")
    parser.add_argument("--max-read-size", type=int, default=5, help="Max read size per page (MB)")
    parser.add_argument("--output", default="links.txt", help="File to write links")
    parser.add_argument("--errors", default="errors.txt", help="File to write errors")
    parser.add_argument("--stats", action="store_true", help="Prints statistics at the end")
    parser.add_argument("--verbose", action="store_true", help="Prints detailed logs")
    parser.add_argument("--append", action="store_true", help="Append to existing output files instead of overwriting them")

    args = parser.parse_args()

    if args.mode == 1 or args.mode == 2:
        if not args.keyword:
            parser.error("modes 1 and 2 require --keyword")

    url = args.url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    file = args.output
    errorFile = args.errors
    keyWord = args.keyword
    maxThread = args.thread
    sleepTime = args.sleep
    crawlerMode = args.mode # 0 -> Normal, 1 -> find X from url, 2 -> find X from content, 3 -> visit only one website
    mode3ThreadN = args.mode3_thread
    maxTime = args.max_time
    maxReadSize = args.max_read_size * 1024 * 1024

    if args.stats:
        statsMode = 1
    else:
        statsMode = 0

    if args.verbose:
        verboseMode = 1
    else:
        verboseMode = 0

    if args.append:
        append = 1
    else:
        append = 0

    startDomain = urlparse(url).netloc.removeprefix("www.")
    executor = ThreadPoolExecutor(max_workers=maxThread)

    domainQueues = {}
    activeDomains = {}
    visited = set()
    stateLock = threading.Lock()
    stopEvent = threading.Event()
    startTime = time.time()
    linkN = 0
    errorN = 0
    maxThreadN = 0
    maxThreadT = 0

    visited.add(url.replace("://www.", "://", 1).rstrip("/"))

    if not append:
        open(file, "w", encoding="utf-8").close()
        open(errorFile, "w", encoding="utf-8").close()
    else:
        try:
            with open(file, "r", encoding="utf-8") as oldLinks:
                for line in oldLinks:
                    line = line.strip()
                    if line:
                        visited.add(line.replace("://www.", "://", 1).rstrip("/"))
        except FileNotFoundError:
            pass

    registerUrl(url)

    try:
        while True:
            time.sleep(1)
            with stateLock:
                if not activeDomains:
                    break

            if maxTime and time.time() - startTime >= maxTime:
                print("Time limit reached, stopping")
                stopEvent.set()
                break

    except KeyboardInterrupt:
        print("Stopping...")
        stopEvent.set()

    executor.shutdown(wait=True)
    print("Crawling finished")

    if statsMode:
        print(f"Links found: {linkN}")
        print(f"Errors: {errorN}")
        print(f"Max number of threads reached: {maxThreadN}, at {maxThreadT:.1f}s")