import os
import time
import hashlib
import signal
import certifi
import ssl
import urllib
from PIL import Image
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from glob import glob
from urllib.parse import unquote
from requests import get
from io import BytesIO
from bing_image_downloader import downloader


number_of_images = 10
GET_IMAGE_TIMEOUT = 2
SLEEP_BETWEEN_INTERACTIONS = 0.1
SLEEP_BEFORE_MORE = 5
IMAGE_QUALITY = 85

output_path = "download"

search_terms = ["pig"]

dirs = glob(output_path + "*")
dirs = [dir.split("/")[-1].replace("_", " ") for dir in dirs]
search_terms = [term for term in search_terms if term not in dirs]

wd = webdriver.Chrome(ChromeDriverManager().install())

class timeout:
    def __init__(self, seconds=1, error_message="Timeout"):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)

def image_size_from_url(url: str):
    try:
        image_raw = get(url)
    except Exception as e:
        return 0, 0
    image = Image.open(BytesIO(image_raw.content))
    return image.size

def fetch_image_urls(
    query: str,
    max_links_to_fetch: int,
    wd: webdriver,
    sleep_between_interactions: int = 1,
):
    def scroll_to_end(wd):
        wd.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(sleep_between_interactions)

    # Build the Google Query.
    search_url = "https://www.google.com/search?safe=off&site=&tbm=isch&source=hp&q={q}&oq={q}&gs_l=img"

    # load the page
    wd.get(search_url.format(q=query))

    # Declared as a set, to prevent duplicates.
    image_urls = set()
    image_count = 0
    results_start = 0
    while image_count < max_links_to_fetch:
        scroll_to_end(wd)

        # Get all image thumbnail results
        thumbnail_results = wd.find_elements_by_css_selector("img.Q4LuWd")
        number_results = len(thumbnail_results)

        print(f"Found: {number_results} search results. Extracting links from {results_start}:{number_results}")

        # Loop through image thumbnail identified
        for img in thumbnail_results[results_start:number_results]:
            # Try to click every thumbnail such that we can get the real image behind it.
            try:
                img.click()
                time.sleep(0.1)
            except Exception:
                continue

            href = img.find_element_by_xpath('./../..').get_attribute('href')
            href = unquote(unquote(href))
            # Get original image url
            src = href[href.find('http', 1):href.find('&tbnid')]

            # Check image size from url
            # width, height = image_size_from_url(src)
            # print(width, height)

            image_urls.add(src)
            # print(src)
            
            # rightElement = wd.find_element_by_id('islsp')
            # try:
            #     jsname = rightElement.find_element_by_xpath('//*[@id="Sva75c"]/div[2]/div[2]/div[2]/div[2]/c-wiz/div[1]/div[1]/div[1]/div[3]/div[1]/a[1]/img[1]').get_attribute("jsname")  
            #     originSrc = rightElement.find_element_by_xpath('//*[@id="Sva75c"]/div[2]/div[2]/div[2]/div[2]/c-wiz/div[1]/div[1]/div[1]/div[3]/div[1]/a[1]/img[1]').get_attribute("src")            
            # except Exception:
            #     try:
            #         originSrc = rightElement.find_element_by_xpath('//*[@id="Sva75c"]/div[2]/div[2]/div[2]/div[2]/c-wiz/div[1]/div[1]/div[1]/div[2]/div[1]/a[1]/img[1]').get_attribute("src")
            #     except Exception:
            #         continue

            # image_urls.add(str(originSrc))

            # Extract image urls
            # actual_images = wd.find_elements_by_css_selector("img.Q4LuWd")
            # for actual_image in actual_images:
                # actual_image.click()
                # src = actual_image.find_element_by_xpath('./../..').get_attribute('jaction')
                # if not src == None:
                #     image_urls.add(src)
                # if actual_image.get_attribute("src") and "http" in actual_image.get_attribute("src"):                    
                #     src = actual_image.find_element_by_xpath('./../..').get_attribute('jaction')
                #     image_urls.add(src)

            image_count = len(image_urls)

            # If the number images found exceeds our `num_of_images`, end the seaerch.
            if len(image_urls) >= max_links_to_fetch:
                print(f"Found: {len(image_urls)} image links, done!")
                break
        else:
            # If we haven't found all the images we want, let's look for more.
            print("Found:", len(image_urls), "image links, looking for more ...")
            time.sleep(SLEEP_BEFORE_MORE)

            # Check for button signifying no more images.
            not_what_you_want_button = ""
            try:
                not_what_you_want_button = wd.find_element_by_css_selector(".r0zKGf")
            except:
                pass

            # If there are no more images return.
            if not_what_you_want_button:
                print("No more images available.")
                return image_urls

            # If there is a "Load More" button, click it.
            load_more_button = wd.find_element_by_css_selector(".LZ4I")
            if load_more_button and not not_what_you_want_button:
                wd.execute_script("document.querySelector('.LZ4I').click();")

        # Move the result startpoint further down.
        results_start = len(thumbnail_results)

    return image_urls


def persist_image(folder_path: str, url: str):
    try:
        print("Getting image")
        # Download the image.  If timeout is exceeded, throw an error.
        file_path = os.path.join(folder_path, hashlib.sha1(url.encode()).hexdigest()[:10] + ".png")
        
        # urllib.request.urlretrieve(url, file_path)
        with urllib.request.urlopen(url, context=ssl.create_default_context(cafile=certifi.where())) as d, open(file_path, "wb") as opfile:
            data = d.read()
            opfile.write(data)
            print(f"SUCCESS - download {url} - as {file_path}")

    except Exception as e:
        print(f"ERROR - Could not download {url} - {e}")

    # try:
    #     # Convert the image into a bit stream, then save it.
    #     image_file = io.BytesIO(image_content)
    #     image = Image.open(image_file).convert("RGB")
    #     # Create a unique filepath from the contents of the image.
    #     file_path = os.path.join(folder_path, hashlib.sha1(image_content).hexdigest()[:10] + ".jpg")
    #     with open(file_path, "wb") as f:
    #         image.save(f, "JPEG", quality=IMAGE_QUALITY)
    #     print(f"SUCCESS - saved {url} - as {file_path}")
    # except Exception as e:
    #     print(f"ERROR - Could not save {url} - {e}")

def search_and_download(search_term: str, target_path="./images", number_images=5):
    # Create a folder name.
    target_folder = os.path.join(target_path, "_".join(search_term.lower().split(" ")))
    target_folder = target_folder.replace(":", "_").replace("*","_")
    # Create image folder if needed.
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    # Open Chrome

    # Search for images URLs.
    res = fetch_image_urls(
        search_term,
        number_images,
        wd=wd,
        sleep_between_interactions=SLEEP_BETWEEN_INTERACTIONS,
    )

    # Download the images.
    if res is not None:
        for elem in res:
            persist_image(target_folder, elem)
    else:
        print(f"Failed to return links for term: {search_term}")

# Loop through all the search terms.
# for term in search_terms:
#     search_and_download(term, output_path, number_of_images)
#     downloader.download(term, limit=number_of_images,  output_dir=output_path, adult_filter_off=True, force_replace=False, timeout=60, verbose=True)

def search_image(search_term: str, number_image: 5, search_engine: str):
    if search_engine == "google":
        search_and_download(search_term, output_path, number_image)
    else:
        downloader.download(search_term, limit=number_image,  output_dir=output_path, adult_filter_off=True, force_replace=False, timeout=60, verbose=True)





