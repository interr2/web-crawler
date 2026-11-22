# Web Crawler by interr

This is a multi-threaded cli web crawler written in Python. It discovers links across the web, can search for a keyword in urls or content. No external dependencies needed.

## Features

- The crawler is multi-threaded, one thread per domain. Maximum thread number is configurable.

- The crawler has 4 different modes; default mode, searching a keyword in urls, searching a keyword in contents, single-site crawling.

- It filters junk domains and parameters.

## Requirements

- Python 3.9 or higher.

## Installation

```
git clone https://github.com/interr2/web-crawler.git
cd web-crawler
```

## Usage

```
python crawler.py <url> [args]
```

or python3 on Linux and MacOS

## How it works

1. The start url gets placed in queue for its domain.
2. Each domain gets a worker thread. Only in mode 3, you can increase thread number.
3. The workers get the page content, extract links, clean and filter them and remove the ones that were already seen and visited.
4. New links are queued under their own domain queues. A new thread will start if a new domain gets discovered.
5. The crawler stops when all queues are empty, the max time limit is reached or you press "Ctrl+C".

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `url` | required | Start url |
| `--mode` | `0` | Crawl mode (`0`, `1`, `2`, `3`) |
| `--keyword` | `""` | Keyword to search for (modes 1 and 2) |
| `--thread` | `100` | Maximum number of threads |
| `--mode3-thread` | `5` | Number of threads used on the single site in mode 3 |
| `--sleep` | `0.5` | Delay between requests, per worker (seconds) |
| `--max-time` | `10` | Maximum run time in seconds (`0` = unlimited) |
| `--max-read-size` | `5` | Maximum amount read per page (MB) |
| `--output` | `links.txt` | File the results are written to |
| `--errors` | `errors.txt` | File failed requests are written to |
| `--stats` | off | Print statistics when finished |
| `--verbose` | off | Print detailed logs while crawling |
| `--append` | off | Append to existing output files instead of overwriting them |

## Modes

| Mode | Name | What it does |
|------|------|--------------|
| `0` | Default | Crawls all discovered links across all domains and writes every new crawlable link to the output file. |
| `1` | Keyword in url | Crawls like mode 0, but only writes links whose url contains the keyword. Matching is case-insensitive and also checks links that are not crawled (e.g. `xmlrpc`, images), so you can search for them. |
| `2` | Keyword in content | Visits every discovered link, searches the page content for the keyword and writes the urls of matching pages. Nothing is filtered out, and text-based non-HTML content (JSON, XML, plain text) is searched as well. |
| `3` | Single site | Crawls only the domain of the start url, using multiple threads (`--mode3-thread`). Other domains are ignored. |
 
Modes 1 and 2 require `--keyword`.

## Examples

```
# Crawl with default settings (stops after 10 seconds)
python crawler.py https://example.com

# Crawl without a time limit (stop with Ctrl+C)
python crawler.py https://example.com --max-time 0

# Find links that contain "shop" in the url
python crawler.py https://example.com --mode 1 --keyword shop --max-time 60

# Find pages whose content contains "free shipping"
python crawler.py https://example.com --mode 2 --keyword "free shipping" --max-time 120

# Crawl only example.com with 5 threads, show stats at the end
python crawler.py https://example.com --mode 3 --max-time 60 --stats

# Show detailed logs and write to custom files
python crawler.py https://example.com --verbose --output result.txt --errors err.txt

# Show all options
python crawler.py -h
```

## Output

- **`links.txt`**: one url per line. In modes 0 and 3 these are all discovered links, in mode 1 the links matching the keyword, in mode 2 the pages whose content matches.
- **`errors.txt`**: failed requests with the error (timeouts, HTTP errors, DNS failures).

With `--stats` you get:
 
```
Links found: 3100
Errors: 7
Max number of threads reached: 100, at 8.4s
```

By default, both files are overwritten on every run, so copy any results you want to keep. With "--append", new results are added to the existing files, and the links already in the output file are loaded as visited so they are not written again. Note that this is not a full resume, the crawl still starts from the given url.

## Things to improve in future (maybe)

- There is no per-domain page limit, so sites with huge url variations can grow the queue so much and slow the system.

- Pages are decoded as UTF-8, so some sites with different encodings may lose some characters.

- The crawler's default User-Agent is Mozilla/5.0

- The code could be more organized.

- The project can be implemented to pip (maybe x2)

## IMPORTANT: Responsible use

This tool can send many requests very quickly, especially with many threads or in mode 3. You should be careful while crawling websites, you may get banned from websites if you are not careful.

You are responsible for how you use this tool

## License

MIT