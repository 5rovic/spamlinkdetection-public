# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class UnprocessedSiteContent(scrapy.Item):
    homepage_url = scrapy.Field()
    page_content = scrapy.Field()
    external_links = scrapy.Field()
    site_category = scrapy.Field()

class ProcessedSiteContent(UnprocessedSiteContent):
    external_links_text = scrapy.Field()
