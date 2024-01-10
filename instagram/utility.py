from django.core.files.base import ContentFile

from apps.instagram.models import Scraper

from selenium.webdriver.common.by import By
from selenium import webdriver

import requests
import logging
import os.path
import random
import time
import os
import re

logger = logging.getLogger('instagram')
logger.setLevel('INFO')


def login(driver: webdriver.Chrome, username: str, password: str):
    time.sleep(5)
    driver.implicitly_wait(30)
    try:
        username_field = driver.find_element(by=By.CSS_SELECTOR, value="input[name='username']")
    except(Exception, ):
        return {
                "status": False,
                "driver": driver,
                "error": "Input for username not found",
            }
    try:
        password_field = driver.find_element(by=By.CSS_SELECTOR, value="input[name='password']")
    except(Exception, ):
        return {
                "status": False,
                "driver": driver,
                "error": "Input for password not found",
            }

    # clear fields before typing
    username_field.clear()
    password_field.clear()

    username_field.send_keys(username)
    time.sleep(2)
    password_field.send_keys(password)
    time.sleep(2)

    driver.implicitly_wait(20)
    try:
        login_btn = driver.find_element(by=By.CSS_SELECTOR, value="button[type='submit']")
    except(Exception, ):
        return {
            "status": False,
            "driver": driver,
            "error": "Submit button not found on login page ",
        }

    login_btn.click()
    time.sleep(10)
    return {"status": True}


def get_image_from_url(photo_link, model_instance, save_destination):
    try:
        content_file = None
        response = requests.get(photo_link)
        binary_content = response.content
        if 200 <= response.status_code < 300:
            content_file = ContentFile(binary_content)
    except(Exception,):
        content_file = None

    if content_file:
        try:
            integer_part = photo_link.split("/")[5]
            integer_part = integer_part.split(".")[0]
            if os.path.exists(BASE_DIR / f'media/{integer_part}.png'):
                os.remove(BASE_DIR / f'media/{integer_part}.png')
            if save_destination == "profile":
                model_instance.image.save(f'{integer_part}.png', content_file)
            elif save_destination == "media":
                model_instance.file_content.save(f'{integer_part}.png', content_file)
            elif save_destination == "cover":
                model_instance.cover.save(f'{integer_part}.png', content_file)
        except Exception as ex:
            print(ex)


def extract_base_url(url):
    match = re.search(r"(https://www\.instagram\.com/[\w\.]+)/?", url)
    if match:
        return match.group(1)
    else:
        return None


def remove_unnecessary_part_from_post_link(instagram_link):
    regex = r"\/p\/\w+\/(.+)"
    match = re.search(regex, instagram_link)
    if match:
        unnecessary_part = match.group(1)
        cleaned_link = instagram_link.replace(unnecessary_part, "")
        return cleaned_link
    else:
        return instagram_link


def convert_string_to_number(str_num):
    if not str_num:
        return None
    try:
        if str_num.endswith('тыс.'):
            num = float(str_num[:-4].replace(',', '.')) * 1000
        elif str_num.endswith('млн'):
            num = float(str_num[:-4].replace(',', '.')) * 1000000
        elif str_num.endswith('K'):
            num = float(str_num[:-1].replace(',', '.')) * 1000
        elif str_num.endswith('M'):
            num = float(str_num[:-1].replace(',', '.')) * 1000000
        else:
            num = float(str_num.replace(',', ' ').replace(' ', ''))
        return int(num)
    except(Exception,):
        return None


def get_element_position(driver, element):
    desired_pos = (element.size['height'] / 2) + element.location['y']
    current_pos = (driver.execute_script('return window.innerHeight') / 2) + driver.execute_script('return window.pageYOffset')
    scroll_y_by = desired_pos - current_pos
    return scroll_y_by


def measure_execution_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"< < < < < < < < < <  Execution time of {func.__name__}: {execution_time} seconds  > > > > > > > > > > \n\n")
        return result
    return wrapper


def get_free_scraper(set_status=True) -> Scraper or bool:
    scrapers = Scraper.objects.filter(
        is_busy=False, is_active=True, is_available=True
    )
    if not scrapers.exists():
        return False
    scraper = random.choice(scrapers)
    if set_status:
        scraper.is_busy = True
        scraper.save()
    return scraper


def finisher(driver: webdriver, session):
    try:
        driver.close()
        driver.quit()
    except(Exception, ):
        pass

    try:
        session.is_busy = False
        session.save()
    except(Exception, ):
        pass
