class PostPaths:
    LIKES_QTY_MODULE = "//a/span[contains(text(), 'like')]"
    LIKES_QTY = 'section > div > div > div > span'
    VIEWS_QTY = "//span[contains(text(), 'view')]/span"
    DATE = 'a > span > time'
    TEXT1 = '.x5yr21d.xw2csxc.x1odjw0f.x1n2onr6 .x193iq5w.xeuugli.x1fj9vlw.x13faqbe.x1vvkbs.xt0psk2.x1i0vuye.xvs91rp.xo1l8bm.x5n08af'
    TEXT2 = "h1[dir='auto']"
    LIKES_LIST = 'section main > div > div > div'
    LIKER_USERNAME = 'a span > div'
    LIKER_IMAGE = 'a:nth-child(2) img'
    LIKER_URL = "div[aria-disabled='true'] a"
    LIKER_FULLNAME = "span:nth-child(2) > span"
