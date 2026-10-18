import httpx
from bs4 import BeautifulSoup
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-IN,en;q=0.9',
}

try:
    with httpx.Client(headers=headers, timeout=12.0, follow_redirects=True) as client:
        r = client.get('https://www.meesho.com/search?q=samsung')
        print('Status:', r.status_code)
        print('Length:', len(r.text))
        soup = BeautifulSoup(r.text, 'html.parser')
        print('Title:', soup.title.string if soup.title else None)

        # Look for next data or script tags
        scripts = soup.find_all('script')
        for s in scripts:
            if s.string and '__NEXT_DATA__' in s.string:
                print('Found __NEXT_DATA__ script!')
            elif s.get('id') == '__NEXT_DATA__':
                print('Found __NEXT_DATA__ element!')

        links = soup.select('a[href*="/p/"]')
        print('Found /p/ links:', len(links))
        if links:
            for l in links[:3]:
                print('Link href:', l.get('href'))
                print('Text:', l.get_text(separator=' ', strip=True)[:100])
except Exception as e:
    print('Error:', e)
