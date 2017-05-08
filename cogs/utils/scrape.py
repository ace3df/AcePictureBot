from bs4 import BeautifulSoup
import requests

def scrape_website(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'
    }
    try:
        r = requests.get(url, timeout=5,  headers=headers)
    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
        return False
    if r.status_code != 200:
        return False  # bad status_code
    if r.content == "":
        return False  # Empty site
    return BeautifulSoup(r.content, 'html5lib')