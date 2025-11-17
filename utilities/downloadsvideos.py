import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import re

def scrape_video_links(url, link_text="English Download"):
    """
    Scrapes all hyperlinks with the specified text from the given URL.
    Prepends the base URL to relative links.
    """
    try:
        # Fetch the webpage content
        response = requests.get(url)
        response.raise_for_status()  # Check for HTTP request errors

        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Create a case-insensitive regular expression to match the link text
        link_text_regex = re.compile(re.escape(link_text), re.IGNORECASE)

        # Find all links with the specified text (case-insensitive match)
        video_links = []
        for a in soup.find_all('a', string=link_text_regex):
            if 'href' in a.attrs:
                # Prepend base URL if the link is relative
                full_url = urljoin(url, a['href'])
                video_links.append(full_url)

        return video_links

    except Exception as e:
        print(f"An error occurred while scraping links: {e}")
        return []

def download_video_series(video_links, output_directory="."):
    """
    Downloads videos from the provided list of links and saves them to the specified directory.
    Displays download progress as a percentage.
    """
    # Create the output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)

    total_files = len(video_links)
    for idx, link in enumerate(video_links, start=1):
        # Get filename from the link
        file_name = link.split('/')[-1]
        file_path = os.path.join(output_directory, file_name)

        print(f"Downloading file {idx}/{total_files}: {file_name} to {output_directory}")

        try:
            # Create response object
            r = requests.get(link, stream=True)
            r.raise_for_status()  # Check for HTTP errors

            # Get the total file size
            total_size = int(r.headers.get('content-length', 0))

            # Download the file in chunks and track progress
            with open(file_path, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1 MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Print progress percentage
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\rProgress: {progress:.2f}% ({downloaded}/{total_size} bytes)", end="")
            
            print(f"\n{file_name} downloaded successfully!\n")

        except Exception as e:
            print(f"Failed to download {file_name}: {e}")

    print("All videos downloaded!")

# Main execution
if __name__ == "__main__":
    # URL of the webpage to scrape
    url = "https://sites.uclouvain.be/ipsp/FilmStim/film.htm"
    
    # Specify the output directory
    output_directory = r"C:\Users\canoz\OneDrive\Masaüstü\EmotionVideos"  # Change this to your desired directory

    # Scrape the video links
    print("Scraping video links...")
    video_links = scrape_video_links(url)

    if video_links:
        print(f"Found {len(video_links)} video links. Starting download...\n")
        download_video_series(video_links, output_directory)
    else:
        print("No video links found!")
