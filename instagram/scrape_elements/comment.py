from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By

from instagram.utility import get_image_from_url
from apps.instagram.models import Profile, Comment
from apps.utils.assistant import Assistant

from ..element_paths.comment import CommentPaths

from bs4 import BeautifulSoup

import logging
import time
import re

insta_comment_logger = logging.getLogger('instagram')
insta_comment_logger.setLevel('INFO')


class CommentData:
    def __init__(self, driver: WebDriver):
        self.driver = driver

    @staticmethod
    def _get_comment_info(comment):
        base_url = "https://www.instagram.com"

        author_username = comment.select_one("a span")
        author_username = author_username.text if author_username else author_username

        author_link_unformatted = comment.select_one(CommentPaths.AUTHOR_LINK_UNFORMATTED)
        author_link_unformatted = author_link_unformatted["href"] if author_link_unformatted else None
        author_link = base_url + author_link_unformatted if author_link_unformatted and base_url not in author_link_unformatted else author_link_unformatted

        author_photo = comment.select_one("img")
        author_photo = author_photo["src"] if author_photo else author_photo

        comment_time_tag = comment.select_one("a time")

        if not comment_time_tag and comment.select_one("div > img"):  # gif appears, pass this comment
            return {}
        elif not comment_time_tag and not comment.select_one("div > img"):
            raise Exception

        comment_date = comment_time_tag['datetime'] if comment_time_tag else None

        comment_likes_element = comment.select_one("span > span")
        comment_likes_text = comment_likes_element.text.lower().replace(",", "") if comment_likes_element else None
        comment_likes_qty = int(re.findall(r'\d+', comment_likes_text)[0]) if comment_likes_text and "like" in comment_likes_text else 0

        comment_url = comment_time_tag.find_parent('a')
        comment_url = comment_url["href"] if comment_url else comment_url

        if comment_url and "/r/" in comment_url:
            comment_id = comment_url.split("/")[6]
        elif comment_url and "/c/" in comment_url:
            comment_id = comment_url.split("/")[4]
        else:
            comment_id = None

        comment_info = {
            "username": author_username,
            "author_photo": author_photo,
            "author_link": author_link,
            "like_count": comment_likes_qty,
            "comment_url": comment_url,
            "comment_id": comment_id,
            "date": comment_date,
        }
        return comment_info

    def get_comments(self, publication):
        checker = 0
        comments_ids_list = []
        while True:  # scroll and open hidden part at the bottom
            if checker % 5 == 0:
                flag = False
                time.sleep(1)
                comment_publ_date = self.driver.find_elements(By.CSS_SELECTOR, value=CommentPaths.COMMENT_PUBL_DATES)
                unique_comment_publ_date = comment_publ_date[len(comments_ids_list):]
                for date in unique_comment_publ_date:
                    try:
                        comment_id = date.find_element(by=By.XPATH, value="./parent::*").get_attribute("href").split("/")[6]
                    except(Exception,):
                        comment_id = None

                    if comment_id and comment_id in comments_ids_list:
                        flag = True
                        break
                    comments_ids_list.append(comment_id)
                if flag:
                    break

            try:  # get scroll element
                self.driver.implicitly_wait(5)
                scroll_element = self.driver.find_element(by=By.CSS_SELECTOR, value=CommentPaths.SCROLL_ELEMENT)
            except(Exception,):
                scroll_element = None

            if scroll_element:
                if "other" in scroll_element.text:
                    break
                self.driver.execute_script("arguments[0].scrollIntoView();", scroll_element)
            else:
                try:
                    hidden_comments_btn = self.driver.find_element(by=By.CSS_SELECTOR, value=CommentPaths.HIDDEN_COMMENTS_BTN)
                except(Exception,):
                    break
                try:
                    hidden_comments_btn.click()
                except Exception as ex:
                    insta_comment_logger.error(f"Error when hidden comments button clicked. {ex}")
                    break

            time.sleep(1)
            checker += 1

        self.driver.find_element(by=By.CSS_SELECTOR, value='body').send_keys(Keys.CONTROL + Keys.HOME)

        view_all_replies_btns = self.driver.find_elements(by=By.XPATH, value=CommentPaths.EXPAND_REPLIES_BTN)
        for button in view_all_replies_btns:  # open all `view all replies` buttons
            while True:
                try:
                    if button.text == "Скрыть ответы" or "Hide" in button.text:
                        break
                except(Exception, ):
                    pass

                try:
                    button.click()
                except(Exception,):
                    break
                time.sleep(0.5)

        comment_publ_dates = self.driver.find_elements(By.CSS_SELECTOR, value=CommentPaths.COMMENT_PUBL_DATES)
        Assistant.send_to_topic(
            topic_key="IS", driver=self.driver,
            text=f"Comments : {len(comment_publ_dates)}\n📰🔗:\t{publication.url}\n📃🔗:\t{self.driver.current_url}",
        )

        try:
            post_module = self.driver.find_element(by=By.CSS_SELECTOR, value=CommentPaths.POST_MODULE)
        except Exception as ex:
            Assistant.send_to_topic(topic_key="IS", text=f"Post module not found. Exceptions itself:  {ex}", driver=self.driver)
            raise ex

        soup = BeautifulSoup(post_module.get_attribute("innerHTML"), 'html.parser')
        comments = soup.select(CommentPaths.COMMENTS)
        time.sleep(3)
        comments_selenium_version = self.driver.find_elements(by=By.CSS_SELECTOR, value=CommentPaths.COMMENTS)

        if len(comments) > 0 and not comments[0].select_one("span > svg[aria-label]"):
            comments = comments[1:]
            comments_selenium_version = comments_selenium_version[1:]

        width_options = []
        for comment in comments_selenium_version:
            comment_dimentions = comment.size
            comment_current_width = comment_dimentions['width']
            if comment_current_width not in width_options:
                width_options.append(comment_current_width)

        parent_comment = None
        for c_counter, comment in enumerate(comments):
            current_comment = comments_selenium_version[c_counter]
            current_comment_width = current_comment.size["width"]
            comment_info = self._get_comment_info(comment)

            if not comment_info.get("comment_url"):
                continue
            else:
                if "https://www.instagram.com" not in comment_info.get("comment_url"):
                    comment_url = "https://www.instagram.com" + comment_info.get("comment_url")
                else:
                    comment_url = comment_info.get("comment_url")

            comment_author, created = Profile.objects.update_or_create(
                url=comment_info.get("author_link"),
                defaults={
                    "username": comment_info.get("username"),
                }
            )
            # Save commenter photo
            get_image_from_url(comment_info.get("author_photo"), comment_author, save_destination="profile")

            try:
                comment_text = comment.select_one("div > div:nth-child(2) > span[dir='auto']").text
            except(Exception,):
                comment_text = None

            comment_obj, created = Comment.objects.update_or_create(
                url=comment_url,
                defaults={
                    "post": publication,
                    "author": comment_author,
                    "text": comment_text,
                    "publish_date": comment_info.get("date"),
                    "reaction_count": comment_info.get("likes_qty"),
                }
            )
            if current_comment_width == width_options[0]:
                parent_comment = comment_obj
            elif current_comment_width == width_options[1] and parent_comment:
                comment_obj.reply_to = parent_comment
                comment_obj.save()
