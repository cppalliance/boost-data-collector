import requests
from bs4 import BeautifulSoup

response = requests.get('https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2026/')
soup = BeautifulSoup(response.text, 'html.parser')

anchor = soup.find('a', id='mailing2026-02')
if not anchor:
    print("Anchor not found")
else:
    table = anchor.find_next('table')
    rows = table.find_all('tr')
    print(f"Found {len(rows)} rows in table after anchor")
    for row in rows[:3]:
        cells = [c.text.strip() for c in row.find_all(['th', 'td'])]
        print(cells)
        # Also print links in first cell
        if row.find('td'):
            links = row.find_all('td')[0].find_all('a')
            print("Links:", [l['href'] for l in links])
