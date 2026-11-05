import requests
from bs4 import BeautifulSoup
import re

def scrape_anime_data(hianime_url):
    """
    Fetches Anime details and Episode list from HiAnime/Aniwatch
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(hianime_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 1. Get Basic Info
    title_tag = soup.find('h2', class_='name')
    img_tag = soup.find('img', class_='film-poster-ratio')
    
    if not title_tag or not img_tag:
        return None
        
    anime_title = title_tag.text.strip()
    image_url = img_tag['src']
    
    # 2. Get Episode List (Usually in a modal or specific div)
    # Note: HiAnime structure changes often, this is a generalized approach
    episodes_list = []
    ep_links = soup.find_all('a', href=re.compile(r'/watch/'))
    
    for link in ep_links:
        href = link.get('href')
        if '/watch?' in href:
            # Extract ID and Episode Number
            parts = href.split('/')
            anime_id = parts[2] if len(parts) > 2 else None
            ep_num = link.text.strip().replace('E', '').strip()
            if anime_id and ep_num.isdigit():
                episodes_list.append({
                    'id': anime_id,
                    'number': int(ep_num),
                    'url': f"https://hianime.to{href}"
                })
    
    return {
        'title': anime_title,
        'image': image_url,
        'episodes': episodes_list
    }

def get_video_source(anime_id, episode_id):
    """
    Scrapes the actual iframe source for a specific episode
    """
    ep_url = f"https://hianime.to/watch/{anime_id}?ep={episode_id}"
    res = requests.get(ep_url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # Find the main player iframe
    iframe = soup.find('iframe', id="main-video-source")
    if iframe:
        return iframe.get('src')
    return None
