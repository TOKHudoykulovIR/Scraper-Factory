from instagram.utility import get_image_from_url, convert_string_to_number, get_element_position
from apps.instagram.models import ScrapingProfile, Profile, Post, Like, Media
from instagram.scrape_elements.comment import CommentData
from apps.utils.assistant import Assistant
from ..element_paths.post import PostPaths

from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By

from instagram.scrape_elements.base import Base

from django.core.files import File
from datetime import timedelta

import requests
import datetime
import logging
import os.path
import time
import re
import io


insta_post_logger = logging.getLogger('instagram')
insta_post_logger.setLevel('INFO')


class PostData(Base):
    def __init__(self, driver: WebDriver, scraper_username):
        super().__init__(driver, scraper_username=scraper_username)
        current_datetime = datetime.datetime.today()
        yesterday = current_datetime - timedelta(days=1)

        self.post_limit = yesterday.date()
        self.post_links = {}

    def _get_post_like_list(self, post_link: str, publication: Post):
        self.driver.implicitly_wait(0)

        base_url = "https://www.instagram.com"

        if 'reel' in post_link:
            post_link = post_link.replace("reel", "p")

        post_like_list_url = post_link + "liked_by/"

        try:
            self.driver.get(post_like_list_url)
            time.sleep(5)
        except Exception as ex:
            return {"status": False, "error": ex}

        try:
            WebDriverWait(self.driver, 30).until(ec.presence_of_all_elements_located((By.CSS_SELECTOR, "a>img")))
        except Exception as ex:
            return {"status": False, "error": ex}

        likes_list = self.driver.find_elements(by=By.CSS_SELECTOR, value=PostPaths.LIKES_LIST)

        for step, liker in enumerate(likes_list):
            liker_info_parameters = {
                "search_source": liker,
                "additional_info": f"Iteration step: {step}. Liker info: {liker.text}"
            }
            liker_username = self._find_element(PostPaths.LIKER_USERNAME, var_name="liker_username", is_important=True, text=True, **liker_info_parameters)
            liker_image = self._find_element(PostPaths.LIKER_IMAGE, var_name="liker_image", is_important=True, attribute="src", **liker_info_parameters)
            liker_link = self._find_element(PostPaths.LIKER_URL, var_name="liker_link", is_important=True, attribute="href", **liker_info_parameters)
            liker_fullname = self._find_element(PostPaths.LIKER_FULLNAME, var_name="liker_fullname", text=True, **liker_info_parameters)

            if liker_link:
                liker_link = base_url + liker_link if base_url not in liker_link else liker_link
            else:
                continue  # liker link is None

            liker_obj, created = Profile.objects.update_or_create(
                url=liker_link,
                defaults={
                    "image": liker_image,
                    "username": liker_username,
                    "fullname": liker_fullname,
                }
            )
            Like.objects.get_or_create(
                publication=publication,
                profile=liker_obj
            )
            time.sleep(1)

    def _get_post_media(self, cover_link):
        self.driver.implicitly_wait(5)
        possible_images = self.driver.find_elements(by=By.CSS_SELECTOR, value='div[role="button"] img[style="object-fit: cover;"]')
        possible_video = self.driver.find_elements(by=By.CSS_SELECTOR, value="div > div video")

        if not possible_images and not possible_video:
            try:  # open unacceptable content
                self.driver.implicitly_wait(3)
                self.driver.find_element(by=By.CSS_SELECTOR, value="div[aria-hidden='true'] button > div").click()
            except(Exception,):
                return [], []

        post_images = []
        post_video = []
        while True:
            self.driver.implicitly_wait(3)
            try:
                saved_image_urls = list(map(lambda x: x["url"], post_images))
                possible_images = self.driver.find_elements(by=By.CSS_SELECTOR, value='div[role="button"] img[style="object-fit: cover;"]')
                for img in possible_images:
                    if img.get_attribute("src") not in saved_image_urls and img.get_attribute("draggable") != "false":
                        post_images.append({"url": img.get_attribute("src")})
            except(Exception,):
                pass

            try:
                saved_video_urls = list(map(lambda x: x["url"], post_video))
                possible_video = self.driver.find_elements(by=By.CSS_SELECTOR, value="div > div video")
                for video in possible_video:
                    if video.get_attribute("src") not in saved_video_urls:
                        post_video.append(
                            {
                                "url": video.get_attribute("src"),
                                "cover": cover_link,
                            }
                        )
            except(Exception,):
                pass

            try:
                next_post_media = self.driver.find_element(by=By.CSS_SELECTOR, value="button[aria-label='Next']")
                next_post_media.click()
                time.sleep(2)
            except(Exception,):
                break
        return post_images, post_video

    def _get_cell_info(self, cell: WebElement, from_section):
        is_pinned_post = False
        clip_or_video_cover = None

        try:
            position = get_element_position(self.driver, cell)  # get cell postion
            self.driver.execute_script("window.scrollBy(0, arguments[0]);", position)  # scroll to cell
            time.sleep(2)
        except(Exception, ):
            return None

        ActionChains(self.driver).move_to_element(cell).perform()  # hover cell to show outer information
        time.sleep(1)

        cell_stats = cell.find_elements(by=By.CSS_SELECTOR, value="div ul li")  # get cell outer information
        if cell_stats:
            comments_qty = cell_stats[0] if len(cell_stats) == 1 else cell_stats[1]
            comments_qty = convert_string_to_number(comments_qty.text)
        else:
            comments_qty = None

        if from_section == "reels":
            try:
                self.driver.implicitly_wait(3)
                post_cover_style_attr = cell.find_element(by=By.CSS_SELECTOR, value="div").get_attribute("style")
                clip_or_video_cover = re.search('url\("(.*?)"\)', post_cover_style_attr).group(1)
            except(Exception,):
                clip_or_video_cover = None
        elif from_section == "publications":
            # get cell type. Can be "Clip", "Video" or "Collection"
            try:
                cell_type = cell.find_element(by=By.CSS_SELECTOR, value="svg")
            except(Exception, ):
                cell_type = None

            if cell_type:
                if cell_type.get_attribute("aria-label") in ["Clip", "Video"]:  # cell is Clip or Video
                    clip_or_video_cover = cell.find_element(by=By.CSS_SELECTOR, value="img").get_attribute("src")
                elif cell_type.get_attribute("aria-label") == "Pinned post icon":  # cell is Pinned Post
                    is_pinned_post = True

        cell_info = (comments_qty, clip_or_video_cover)
        return cell_info, is_pinned_post

    def get_post_links(self, profile_obj):
        self.driver.implicitly_wait(0)
        breaker = False
        cycle_limit = 2
        cycle_counter = 0
        pinned_cells_qty = 0

        if profile_obj.publications_qty == 0:  # Check whether profile has posts
            return True

        while cycle_limit:
            post_cells = self.driver.find_elements(By.CSS_SELECTOR, "article > div:nth-child(1) a")  # get post cells
            if not post_cells:
                return True

            current_post_cells_qty = len(post_cells)

            for cell in post_cells:
                post_url = cell.get_attribute("href")

                if post_url not in self.post_links:
                    cell_info, is_pinned_post = self._get_cell_info(cell, from_section="publications")

                    if cell_info:
                        self.post_links[post_url] = cell_info
                    else:
                        insta_post_logger.error("Cannot move to post for retrieving outer information")
                        return False

                    cell_cover = self._find_element("img", search_source=cell, is_important=True, var_name="cell_cover")
                    cell_cover_alt_attr = cell_cover.get_attribute("alt")  # get post publish date

                    try:
                        match = re.match(r"Photo (?:shared by (.+?)on|by (.+?) on) (\w+ \d{1,2}, \d{4})(.+)", cell_cover_alt_attr)
                    except(Exception, ):
                        match = None

                    if match:
                        post_publish_date = datetime.datetime.strptime(match.group(3), '%B %d, %Y').date()
                    else:
                        post_publish_date = self._get_post_publish_date(cell)
                        if post_publish_date is False:
                            return False
                        else:
                            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()

                    if is_pinned_post:
                        continue

                    if isinstance(self.post_limit, datetime.date) and isinstance(post_publish_date, datetime.date):
                        if post_publish_date <= self.post_limit:
                            breaker = True
                            break
                    elif len(self.post_links) > 20:
                        breaker = True
                        break

            if breaker:
                break

            try:
                loader = self.driver.find_element(by=By.CSS_SELECTOR, value="div[data-visualcompletion='loading-state']")
            except(Exception, ):
                loader = None
                cycle_limit -= 1

            if loader:
                try:
                    position = get_element_position(self.driver, loader)
                    self.driver.execute_script("window.scrollBy(0, arguments[0]);", position)
                    time.sleep(2)
                    cycle_limit = 2
                except(Exception, ):
                    cycle_limit -= 1

            if cycle_counter % 3 == 0:
                if pinned_cells_qty == current_post_cells_qty:
                    break
                else:
                    pinned_cells_qty = current_post_cells_qty
            cycle_counter += 1

        insta_post_logger.info(f' 3.1  ~ ~ ~ ~ ({profile_obj.scraping_profile.id})  |  (Ready post links for scraping: {len(self.post_links)})')
        Assistant.send_to_topic(
            topic_key="IS",
            text=f"🤖:\t{self.scraper_username}\n👤:\t{profile_obj.username}\nAmount of 📰 links:\t{len(self.post_links)}",
            driver=self.driver
        )
        return True

    def get_post_info(self, profile_obj):
        self.driver.implicitly_wait(0)

        for step, post_items in enumerate(self.post_links.items()):
            views_qty = None
            post_link = post_items[0]
            post_comment_qty = post_items[1][0]

            try:
                self.driver.get(post_link)
                time.sleep(5)
            except Exception as ex:
                return {"status": False, "error": ex}

            try:
                WebDriverWait(self.driver, 30).until(ec.presence_of_element_located((By.CSS_SELECTOR, 'section main')))
            except Exception as ex:
                return {"status": False, "error": ex}

            Assistant.send_to_topic(
                topic_key="IS",
                text=f"🤖:\t{self.scraper_username}\n👤:\t{profile_obj.username}\n📰🔗:\t{post_link}\n📃🔗:\t{self.driver.current_url}",
                driver=self.driver
            )

            date = self._find_element(PostPaths.DATE, attribute="datetime", is_important=True)
            text = self._find_element(PostPaths.TEXT2, text=True, var_name="text")

            if not text:
                text = self._find_element(PostPaths.TEXT1, text=True, var_name="text")

            if text:
                text_for_log = text[:30]
            else:
                text = None
                text_for_log = None

            try:
                likes_qty_module = self.driver.find_element(By.XPATH, value=PostPaths.LIKES_QTY_MODULE)
            except(Exception, ):
                likes_qty_module = None

            if likes_qty_module:
                numeric_parts = re.findall(r"\d+", likes_qty_module.text)
                merge_part = "".join(numeric_parts)
                likes_qty = convert_string_to_number(merge_part)
            else:
                try:
                    views_qty_element = self.driver.find_element(By.XPATH, value=PostPaths.VIEWS_QTY)
                except(Exception, ):
                    views_qty_element = None

                if views_qty_element:
                    views_qty = convert_string_to_number(views_qty_element.text)
                    views_qty_element.click()

                try:
                    likes_qty = self.driver.find_element(By.CSS_SELECTOR, value=PostPaths.LIKES_QTY)
                except(Exception, ):
                    likes_qty = None

                if likes_qty:
                    likes_qty = convert_string_to_number(likes_qty.text)
                    if views_qty:
                        try:
                            self.driver.execute_script("arguments[0].click();", views_qty_element)
                        except(Exception,):
                            pass

            parameters = {
                "topic_key": "IS",
                "text": f"🔄:\t{step + 1} of {len(self.post_links)}\n🤖:\t{self.scraper_username}\n👤:\t{profile_obj.username}\n\n"
                        f"📰 link:\t{post_link}\n📅:\t{date}\n💬:\t{post_comment_qty}\n❤️:\t{likes_qty}\n👀:\t{views_qty}\n📝:\t{text_for_log}...",
            }
            Assistant.send_to_topic(**parameters)

            publication, created = Post.objects.update_or_create(
                url=post_link,
                defaults={
                    "comment_count": post_comment_qty,
                    "publish_date": date,
                    "reaction_count": likes_qty,
                    "view_count": views_qty,
                    "post_type": Post.PostType.POST,
                    "author": profile_obj.profile_data_obj,
                    "text": text,
                }
            )
            """
            Comment scraper below
            """
            comment_data_obj = CommentData(driver=self.driver)
            if post_comment_qty and post_comment_qty != 0:
                comment_data_obj.get_comments(publication)
            else:
                comment_data_obj.get_comments(publication)

            """
            Post media scrape below
            """
            post_images, post_video = self._get_post_media(post_items[1][1])  # method to get media from the post

            """
            Post like list scrape below 
            """
            if likes_qty and likes_qty > 0:  # method to get post liker list
                self._get_post_like_list(post_link, publication)
            else:
                self._get_post_like_list(post_link, publication)

            scraping_account = ScrapingProfile.objects.get(url=profile_obj.scraping_profile_url)
            if not publication.media.exists():
                for image_data in post_images:
                    image, created = Media.objects.get_or_create(
                        url=image_data.get("url"),
                        defaults={"content_type": Media.IMAGE}
                    )
                    get_image_from_url(image_data.get("url"), image, save_destination="media")

                    try:
                        publication.media.add(image)
                    except Exception as ex:
                        print(f"Error during assigning image to post {ex}")

                for video_data in post_video:
                    video_url = video_data.get("url")
                    video_cover = video_data.get("cover")

                    video, created = Media.objects.get_or_create(
                        url=video_url,
                        defaults={"content_type": Media.VIDEO}
                    )
                    get_image_from_url(video_cover, video, save_destination="cover")

                    if scraping_account.is_collect_post_video and "blob:" not in video_url:
                        try:
                            desired_part = video_data.get("url").split('.mp4')[0].split('/')[-1]
                            filename = desired_part + ".mp4"
                            response = requests.get(video_data.get("url"), stream=True)
                            video_file = io.BytesIO(response.content)

                            django_file = File(video_file)
                            if os.path.exists(BASE_DIR / f'media/{filename}'):
                                os.remove(BASE_DIR / f'media/{filename}')
                            video.file_content.save(os.path.basename(BASE_DIR / f'media/{filename}'), django_file, save=True)
                        except(Exception,):
                            pass
                    publication.media.add(video)
            publication.save()
        Assistant.send_to_topic(topic_key="IS", text=f"🔼   🔼   🔼   🔼\n\n🤖:\t{self.scraper_username}\n👤🔗:\t{profile_obj.scraping_profile_url}\n\n🏁   🏁   🏁   🏁")
        return {"status": True}

    def _get_post_publish_date(self, cell):
        try:
            cell.click()
        except Exception as ex:
            insta_post_logger.error(f"Error when cell clicked. _get_post_publish_date. {ex}")
            return False

        time.sleep(1)

        try:  # check page loading
            WebDriverWait(self.driver, 10).until(ec.presence_of_element_located((By.CSS_SELECTOR, "article a > span > time")))
        except Exception as ex:
            insta_post_logger.error(f"Wait failed. _get_post_publish_date. {ex}")
            return False

        try:
            post_publish_date_raw = self.driver.find_element(by=By.CSS_SELECTOR, value="article a > span > time").get_attribute("title")
        except Exception as ex:
            insta_post_logger.error(f"Post(modal) publish date not found. _get_post_publish_date. {ex}")
            return False

        try:
            post_publish_date = datetime.datetime.strptime(post_publish_date_raw, '%b %d, %Y').date()
        except Exception as ex:
            insta_post_logger.error(f"Cannot format raw date. _get_post_publish_date. {ex}")
            return False

        return post_publish_date
