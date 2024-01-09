from apps.instagram.utility import get_image_from_url, convert_string_to_number
from apps.instagram.models import Category, ScrapingProfile, Profile
from apps.instagram.scraper.base import Base
from apps.utils.assistant import Assistant

from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

from ..element_paths.account import AccountPaths

from typing import Literal
import logging

import time


insta_logger = logging.getLogger('instagram')
insta_logger.setLevel('INFO')


class ProfileData(Base):
    def __init__(self, driver: WebDriver, scraping_profile: ScrapingProfile, scraper_username=None):
        super().__init__(driver, scraper_username)
        self.scraping_profile = scraping_profile
        self.scraping_profile_url = scraping_profile.url
        self.applied_link = None
        self.fullname = None
        self.category = None
        self.about = None
        self.profile = None
        self.username = None
        self.user_photo = None
        self.followers_qty = None
        self.publications_qty = None
        self.subscriptions_qty = None
        self.is_confirmed = None
        self.profile_data_obj = None

    def _get_profile_cell_info(self, connection_profiles: list[WebElement], scraped_profile: Profile, connection: Literal['follower', 'subscription']):
        for counter, profile in enumerate(connection_profiles):
            profile_photo = self._find_element("img", attribute="src", search_source=profile)
            profile_link = self._find_element("a", attribute="href", search_source=profile)

            self.driver.implicitly_wait(5)
            profile_fullname_elements = profile.find_elements(by=By.CSS_SELECTOR, value="div:nth-child(2) span:nth-child(2)")

            if profile_fullname_elements:
                profile_fullname = ''.join([element.text for element in profile_fullname_elements])
                profile_fullname = None if not profile_fullname else profile_fullname
            else:
                profile_fullname = None

            profile_username_tag = self._find_element("a span > div", search_source=profile)

            if profile_username_tag:
                confirmed_profile_icon = False
                try:
                    profile_username = profile_username_tag.get_attribute('innerHTML').split("<")[0]
                except(Exception,):
                    profile_username = None
            else:
                profile_username = None
                confirmed_profile_icon = False

            try:
                profile_obj, created = Profile.objects.update_or_create(
                    url=profile_link,
                    defaults={
                        "username": profile_username,
                        "fullname": profile_fullname,
                        "is_confirmed": confirmed_profile_icon,
                    })
            except(Exception,):
                profile_obj = None

            if profile_obj:
                get_image_from_url(profile_photo, profile_obj, save_destination="profile")
                if connection == "follower":
                    scraped_profile.followers.add(profile_obj)
                elif connection == "subscription":
                    scraped_profile.subscriptions.add(profile_obj)

        self.driver.execute_script("window.history.go(-1)")
        time.sleep(3)

    def get_user_main_info(self):
        self.driver.implicitly_wait(0)  # set to default

        try:  # open profile page
            self.driver.get(self.scraping_profile_url)
            time.sleep(5)
        except Exception as ex:
            insta_logger.error(ex)
            return False

        try:  # check page loading
            WebDriverWait(self.driver, 60).until(ec.presence_of_element_located((By.CSS_SELECTOR, "main[role='main']")))
        except Exception as ex:
            insta_logger.error(ex)
            return False

        time.sleep(1)

        try:  # Check whether Profile is available
            self.driver.find_element(by=By.XPATH, value=AccountPaths.AVALABLE)
            self.scraping_profile.is_available = False
            self.scraping_profile.save()
            insta_logger.error("Given profile isn\'t available")
            return False
        except(Exception, ):
            self.scraping_profile.is_available = True

        try:  # check page loading
            WebDriverWait(self.driver, 60).until(ec.presence_of_element_located((By.CSS_SELECTOR, "header img")))
        except Exception as ex:
            insta_logger.error(ex)
            return False

        time.sleep(1)

        paremeters = {
            "text": True,
            "is_important": True
        }

        self.username = self._find_element(AccountPaths.USERNAME1, var_name="username", **paremeters)
        self.user_photo = self._find_element(AccountPaths.PHOTO, var_name="user_photo", attribute="src", is_important=True)
        followers_qty = self._find_element(AccountPaths.FOLLOWERS_QTY, var_name="followers_qty", **paremeters)
        publications_qty = self._find_element(AccountPaths.PUBLICATIONS_QTY, var_name="followers_qty", **paremeters)
        subscriptions_qty = self._find_element(AccountPaths.SUBSCRIPTIONS_QTY, var_name="subscriptions_qty", **paremeters)

        self.followers_qty = convert_string_to_number(followers_qty)
        self.publications_qty = convert_string_to_number(publications_qty)
        self.subscriptions_qty = convert_string_to_number(subscriptions_qty)

        try:  # Check whether profile is private
            self.driver.find_element(by=By.XPATH, value=AccountPaths.PRIVATE)
            is_private = True
        except NoSuchElementException:
            is_private = False
        except Exception as ex:
            insta_logger.error(ex)
            return False

        if is_private:
            try:
                self.username = self.driver.find_element(by=By.CSS_SELECTOR, value=AccountPaths.USERNAME2).text
            except Exception as ex:
                insta_logger.error(ex)
                return False

            profile, created = Profile.objects.update_or_create(
                url=self.scraping_profile_url,
                defaults={
                    "username": self.username,
                    "follower_count": self.followers_qty,
                    "publication_count": self.publications_qty,
                    "subscriptions_count": self.subscriptions_qty,
                    "is_private": True
                }
            )
            get_image_from_url(self.user_photo, profile, save_destination="profile")
            return True

        try:  # get verified sign
            confirmation_sign = self.driver.find_element(By.CSS_SELECTOR, value='section svg[aria-label="Verified"]')
        except(Exception, ):
            confirmation_sign = None

        self.is_confirmed = bool(confirmation_sign)

        Assistant.send_to_topic(
            topic_key="IS",
            driver=self.driver,
            text=f"🤖:\t{self.scraper_username}\n👤🔗:\t{self.scraping_profile_url}\n\n👤:\t{self.username}\n"
                 f"📰 num:\t{publications_qty}\nFoll's:\t{followers_qty}\nSubsc's:\t{subscriptions_qty}\n✅:\t{self.is_confirmed}",
        )

        try:
            self.about = self.driver.find_element(By.CSS_SELECTOR, value=AccountPaths.ABOUT).text
        except(Exception, ):
            self.about = None

        try:
            self.fullname = self.driver.find_element(By.CSS_SELECTOR, value=AccountPaths.FULLNAME).text
        except(Exception, ):
            self.fullname = None

        try:
            self.applied_link = self.driver.find_element(By.XPATH, value=AccountPaths.APPLIED_LINK).get_attribute("href")
        except(Exception, ):
            self.applied_link = None

        try:
            category = self.driver.find_element(By.CSS_SELECTOR, value=AccountPaths.CATEGORY)
        except(Exception, ):
            category = None

        if category:
            self.category, created = Category.objects.get_or_create(name=category.text)

        profile, created = Profile.objects.update_or_create(
            url=self.scraping_profile_url,
            defaults={
                "about": self.about,
                "username": self.username,
                "fullname": self.fullname,
                "category": self.category,
                "is_confirmed": self.is_confirmed,
                "follower_count": self.followers_qty,
                "applied_link": self.applied_link,
                "publication_count": self.publications_qty,
                "subscriptions_count": self.subscriptions_qty,
            }
        )
        self.profile_data_obj = profile
        get_image_from_url(self.user_photo, profile, save_destination="profile")
        return True

    def get_followers(self, profile: Profile):
        try:  # open followers list
            self.driver.get(profile.url + "followers/")
        except Exception as ex:
            return {"status": False, "error": ex}

        path_to_loader = "div[role='dialog']:nth-child(2) > div div:nth-child(2) > div:nth-child(3)"  # for hidden
        follower_cells = "div[role='dialog'] div:nth-child(2) > div div[style] > div[style] > div"

        try:  # check whether followers is hidden
            self.driver.implicitly_wait(8)
            loader = self.driver.find_element(by=By.CSS_SELECTOR, value=path_to_loader)
        except(Exception,):
            loader = None

        if loader:
            profile.is_followers_hidden = True
            profile.save()
        else:
            path_to_loader = "div[role='dialog']:nth-child(2) > div > div > div:nth-child(2) > div:nth-child(2)"

        self._scroll_module(path_to_loader, follower_cells)  # scroll followers module
        followers = self.driver.find_elements(by=By.CSS_SELECTOR, value=follower_cells)  # get follower cells
        self._get_profile_cell_info(followers, profile, connection="follower")  # save follower cells data

    def get_subscriptions(self, profile: Profile):
        response = self._open_url(profile.url + "following/")  # open subscriptions list
        if not response.get("status"):
            return response

        subscription_cells = "div[role='dialog'] div[role='tablist'] + div > div > div > div[class]"
        path_to_loader = "div[role='dialog']:nth-child(2) > div > div > div:nth-child(3) > div:nth-child(2)"

        self._scroll_module(path_to_loader, subscription_cells)
        subscriptions = self.driver.find_elements(by=By.CSS_SELECTOR, value=subscription_cells)
        self._get_profile_cell_info(subscriptions, profile, connection="subscription")
