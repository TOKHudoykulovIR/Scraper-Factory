class AccountPaths:
    AVALABLE = '//*[contains(text(),"Sorry, this page isn\'t available")]'
    USERNAME1 = 'header section h2'
    USERNAME2 = 'header section h1'
    PHOTO = "header img[alt*='rofile p']"
    FOLLOWERS_QTY = 'section ul li:nth-child(2) span span'
    PUBLICATIONS_QTY = 'section ul li:nth-child(1) span span'
    SUBSCRIPTIONS_QTY = 'section ul li:nth-child(3) span span'
    PRIVATE = "//*[text()='This account is private']"
    VERIFIED = 'section svg[aria-label="Verified"]'
    CATEGORY = "header section div > div > div[dir='auto']"
    FULLNAME = "section > ul + div span[dir='auto']"
    ABOUT = "section h1[dir='auto']"
    APPLIED_LINK = "//*[name()='svg'][@aria-label='Link icon']/parent::*/following-sibling::*"
