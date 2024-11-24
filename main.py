import sqlite3
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests
import time
from requests.exceptions import RequestException
import re


def extract_language_article_urls(html_content):
    """
    Extract URLs of English Wikipedia articles about individual languages.
    
    Args:
        html_content (str): HTML content of the language index page
        
    Returns:
        list: List of URLs to Wikipedia articles about individual languages
    """
    # Create BeautifulSoup object
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Base Wikipedia URL
    base_url = "https://en.wikipedia.org"
    
    # Find all links in the main content area
    language_urls = set()
    
    # Look for links that likely point to language articles
    # These typically contain "language" or end in "ese", "ish", etc.
    language_indicators = [
        "language", "ese", "ish", "ian", "ish", "ic", 
        "Language", "speech", "tongue"
    ]
    
    for link in soup.find_all('a'):
        href = link.get('href', '')
        title = link.get('title', '')
        
        # Only process internal Wikipedia links
        if href.startswith('/wiki/') and not any(x in href for x in [':', 'List_of', 'Index_of']):
            # Check if the link text or title suggests it's about a language
            if any(indicator in title for indicator in language_indicators):
                full_url = urljoin(base_url, href)
                language_urls.add((full_url, title))
    
    # Sort by title and return just the URLs
    return [url for url, title in sorted(language_urls, key=lambda x: x[1])]


def extract_language_article_urls_from_file():
    with open('language_index.html', 'r', encoding='utf-8') as file:
        html_content = file.read()
        
    urls = extract_language_article_urls(html_content)
    return urls


def extract_language_info(html_content):
    # Create BeautifulSoup object
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the infobox table
    infobox = soup.find('table', class_='infobox')
    if not infobox:
        return {}
    
    # Initialize dictionary for language info
    info = {}
    
    # Get language name from the infobox header
    language_name = infobox.find('th', class_='infobox-above')
    if language_name:
        info['name'] = language_name.text.strip()
    
    # Dictionary mapping field labels to keys in our result
    field_mappings = {
        # Basic Info
        'Native speakers': 'native_speakers',
        'Speakers': 'native_speakers',
        'Language family': 'language_family',
        'Standard forms': 'standard_forms',
        'Dialects': 'dialects',
        'Glottolog': 'glottolog',
    }
    
    # Extract info for each field by looking at all table rows
    for row in infobox.find_all('tr'):
        # Find the label cell
        label_cell = row.find(['th', 'div'], class_=['infobox-label'])
        if not label_cell:
            continue
            
        label = label_cell.get_text().strip()
        
        # Check if this is a field we want to capture
        if label in field_mappings:
            # Get the data cell
            data_cell = row.find('td', class_='infobox-data')
            if data_cell:
                # Get the basic text value first
                value = data_cell.get_text().strip()
                
                # Special handling for language family and dialects - convert to arrays
                if label in ['Language family', 'Dialects']:
                    parts = []
                    for link in data_cell.find_all('a'):
                        text = link.get_text().strip()
                        if text:  # Only add non-empty strings
                            parts.append(text)
                    value = parts if parts else [value]
                
                # Special handling for native speakers count
                elif label in ['Native speakers', 'Speakers']:
                    try:
                        # Get all text from the data cell
                        text = data_cell.get_text().strip()
                        
                        # Check for "No speakers" only at the start of the text
                        if text.lower().split()[0] == 'no':
                            value = 0
                        else:
                            # First check if there's an L1/L2 breakdown
                            l1_element = data_cell.find('a', title='First language')
                            if l1_element:
                                # Find the first number after the L1 label
                                l1_text = l1_element.find_next_sibling(text=True)
                                if l1_text:
                                    matches = re.findall(r'(\d[\d,]*(?:\.\d+)?)\s*(billion|million|thousand)?', l1_text)
                                    if matches:
                                        num_str, unit = matches[0]
                                        num = float(num_str.replace(',', ''))
                                        multiplier = {
                                            'billion': 1000000000,
                                            'million': 1000000,
                                            'thousand': 1000,
                                            '': 1
                                        }[unit or '']
                                        value = int(num * multiplier)
                            else:
                                # Original logic for when there's no L1/L2 breakdown
                                matches = re.findall(r'(\d[\d,]*(?:\.\d+)?)\s*(billion|million|thousand)?', text)
                                if matches:
                                    largest_num = 0
                                    for num_str, unit in matches:
                                        num = float(num_str.replace(',', ''))
                                        multiplier = {
                                            'billion': 1000000000,
                                            'million': 1000000,
                                            'thousand': 1000,
                                            '': 1
                                        }[unit or '']
                                        current_num = int(num * multiplier)
                                        largest_num = max(largest_num, current_num)
                                    value = largest_num
                                else:
                                    continue  # Skip if no numbers found
                        
                        info[field_mappings[label]] = value
                    except (ValueError, IndexError, AttributeError) as e:
                        print(f"Error parsing speakers count: {e}")
                        continue  # Skip if can't parse
                
                # Default handling for other fields - clean up whitespace
                else:
                    value = ' '.join(value.split())
                
                info[field_mappings[label]] = value
    
    return info


def create_language_table():
    """Create the languages table if it doesn't exist"""
    conn = sqlite3.connect('languages.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS languages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            url TEXT,
            native_speakers INTEGER,
            language_family JSON,
            standard_forms TEXT,
            dialects JSON,
            glottolog TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create an index on the name column
    c.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_languages_name 
        ON languages(name)
    ''')
    
    conn.commit()
    conn.close()

def save_language_info(info):
    """Save language information to SQLite database"""
    if not info or 'name' not in info:  # Skip if no name
        return
        
    conn = sqlite3.connect('languages.db')
    c = conn.cursor()
    
    # Convert arrays to JSON strings for storage
    if 'language_family' in info:
        info['language_family'] = json.dumps(info['language_family'])
    if 'dialects' in info:
        info['dialects'] = json.dumps(info['dialects'])
    
    try:
        # Try to insert, if fails due to duplicate, update instead
        fields = ', '.join(info.keys())
        placeholders = ', '.join(['?' for _ in info])
        update_fields = ', '.join([f"{k} = ?" for k in info.keys() if k != 'name'])
        
        sql = f'''
            INSERT INTO languages ({fields})
            VALUES ({placeholders})
            ON CONFLICT(name) DO UPDATE SET
            {update_fields}
        '''
        
        # For UPDATE we need values twice: once for INSERT, once for UPDATE
        values = list(info.values())
        update_values = [v for k, v in info.items() if k != 'name']
        
        c.execute(sql, values + update_values)
        conn.commit()
        print(f"Successfully saved/updated information for {info.get('name', 'unknown language')}")
    except sqlite3.Error as e:
        print(f"Error saving to database: {e}")
    finally:
        conn.close()

def verify_saved_data():
        # Verify the saved data
    conn = sqlite3.connect('languages.db')
    c = conn.cursor()
    c.execute('SELECT * FROM languages ORDER BY created_at DESC')
    results = c.fetchall()
    conn.close()
    
    if results:
        columns = ['id', 'name', 'url', 'native_speakers', 'language_family', 'standard_forms', 'dialects', 'glottolog', 'created_at']
        print("\nSaved data:")
        for result in results:
            saved_data = dict(zip(columns, result))
            print("\nLanguage Entry:")
            for key, value in saved_data.items():
                # Convert JSON strings back to arrays for display
                if key in ['language_family', 'dialects'] and value:
                    value = json.loads(value)
                print(f"{key}: {value}")

def extract_and_store_language_info(html_content, url):
    info = extract_language_info(html_content)
    if info:
        info['url'] = url
    save_language_info(info)

def get_html_content(url):
    """
    Fetch HTML content from a given URL with error handling and rate limiting.
    
    Args:
        url (str): URL to fetch content from
        
    Returns:
        str: HTML content of the page, or empty string if fetch fails
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Add delay to respect Wikipedia's rate limits
        time.sleep(1)
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
        
    except RequestException as e:
        print(f"Error fetching {url}: {e}")
        return ""

def main():
    # Create the database table
    create_language_table()
    
    urls = extract_language_article_urls_from_file()

    # uncomment to test with only a few URLs
    # urls = ['https://en.wikipedia.org/wiki/Arabic', 'https://en.wikipedia.org/wiki/Anatolian_Arabic']
    
    for url in urls:
        html_content = get_html_content(url)
        extract_and_store_language_info(html_content, url)
    
    verify_saved_data()
    

if __name__ == "__main__":
    main()