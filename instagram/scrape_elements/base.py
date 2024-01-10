from typing import Literal

from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

import logging
import time

logger = logging.getLogger('instagram')
logger.setLevel('INFO')


class Base:
    def __init__(self, driver: WebDriver, scraper_username=None):
        self.driver = driver
        self.exceptions = {}
        self.scraper_username = scraper_username

    def _scroll_module(self, path_to_loader, cell_selector):
        while True:
            self.driver.implicitly_wait(5)
            profile_cell_qty = self.driver.find_elements(by=By.CSS_SELECTOR, value=cell_selector)
            if len(profile_cell_qty) >= 500 or not profile_cell_qty:
                break

            try:
                self.driver.implicitly_wait(5)
                scroll_element = self.driver.find_element(by=By.CSS_SELECTOR, value=path_to_loader)
            except (Exception,):
                break

            condition_1 = "other" in scroll_element.text.lower()
            condition_2 = scroll_element.text.lower() in ["suggested for you", "рекомендации для вас"]

            try:
                self.driver.implicitly_wait(2)
                scroll_element.find_element(by=By.CSS_SELECTOR, value="h4")
                condition_3 = True
            except (Exception,):
                condition_3 = False

            if any([condition_1, condition_2, condition_3]):
                break

            time.sleep(0.5)
            try:
                self.driver.execute_script("arguments[0].scrollIntoView();", scroll_element)
                time.sleep(1)
            except (Exception,):
                pass

    def _find_element(
            self,
            path: str,
            text=False,
            var_name=None,
            attribute: Literal['src', 'href', 'datetime'] = None,
            search_by=By.CSS_SELECTOR,
            additional_info=None,
            **kwargs
    ):
        search_source = kwargs.get('search_source', self.driver)

        try:
            self.driver.implicitly_wait(0)
            web_element = search_source.find_element(by=search_by, value=path)
        except Exception as ex:
            log_content = f"Web element not found ⚠️. \n" \
                          f"Scraper 🤖:  {self.scraper_username}. \n" \
                          f"Searching variable 🔤:  {var_name}. \n" \
                          f"Page url 🔗:  {self.driver.current_url}. \n" \
                          f"Exception itself 🚫:  {ex.__str__().split('{')[1].split('}')[0].rstrip()}. \n" \
                          f"Additional info  ℹ️:  {additional_info}. \n"
            logger.warning(log_content.replace("\n", ""))
            return None

        if attribute:
            response = web_element.get_attribute(attribute)
        elif text:
            response = web_element.text
        else:
            response = web_element
        return response

    def _open_url(self, url, wait_time=5):
        try:
            self.driver.implicitly_wait(60)
            self.driver.get(url)
            time.sleep(wait_time)
            return {"status": True}
        except Exception as ex:
            return {"status": False, "error": ex}
