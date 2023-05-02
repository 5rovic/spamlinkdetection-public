import re
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import scrapy
from twisted.internet.error import DNSLookupError
from twisted.internet.error import TimeoutError, TCPTimedOutError
from katalogsites.items import UnprocessedSiteContent, ProcessedSiteContent

from bs4 import BeautifulSoup

class KatalogSitesSpider(scrapy.Spider):
    """
    Pauk koji posjecuje stranice s www.hr kataloga.
    TODO: popraviti probleme
        - if anchor_text.split()[0].isalpha(): - index out of range
        - soup.body.stripped_strings - body je None
        - dnslookup errori i timeout errori
        - token = line.split()[2] - List Index out of range
        - ako je page_content prazan javlja 'NoneType' object is not callable
        -- gornji su popravljeni valjda?

        - provjeriti ima li anchor tag title atribut - ako ima, to uzeti umjesto anchor texta ili alt texta?
            - ne, izgleda da nije bitno (googleati "link title attribute + SEO") 
    """
    name = "hrsites"
    
    custom_settings = {
        'DEPTH_LIMIT': 1,
        'RETRY_ENABLED': False,
        'LOG_LEVEL': 'INFO',
        'DOWNLOAD_TIMEOUT': 20,
        'ROBOTSTXT_OBEY': False,
    }

    def read_wwwhr_xml(self, xml_fullpath):
        sites = dict()
        with open(xml_fullpath, "rb") as xmlfile:
            tree = ET.parse(xmlfile)
            root = tree.getroot()
            for website in root.findall('website'):
                site_url = website.find('site_url').text.strip()
                # site_hostname = urlparse(site_url).hostname 
                # if site_hostname.endswith("hr"): 
                subcategory = website.find('subcategory').text
                sites[site_url] = subcategory
        return sites

    def __init__(self, xml_path=None, *a, **kwargs):
        super(KatalogSitesSpider, self).__init__(*a, **kwargs)

        self.sites = self.read_wwwhr_xml(xml_path)
        if not self.sites:
            raise ValueError("No urls given")
        else:
            self.start_urls = self.sites.keys()

    def start_requests(self):
        for u, cat in self.sites.items():
            yield scrapy.Request(u, 
                callback=self.parse_homepage, 
                cb_kwargs=dict(category=cat), 
                errback=self.errback_homepage
            )

    def errback_homepage(self, failure):
        # self.logger.error(repr(failure))

        if failure.check(DNSLookupError):
            request = failure.request
            self.logger.error('DNSLookupError on %s', request.url)

        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error('TimeoutError on %s', request.url)
        
        else:
            self.logger.error(repr(failure))
    
    def parse_homepage(self, response, category):
        soup = BeautifulSoup(response.body, 'html.parser')
        page_url = response.url
        page_hostname = urlparse(page_url).hostname
        external_links = []
        internal_links = []

        for anchor_element in soup.find_all('a'):
            
            if "rel" in anchor_element.attrs and anchor_element.attrs["rel"] == "nofollow":
                continue

            link_hostname = None
            try:
                if re.match("(^http://)|(^https://)", anchor_element['href']):
                    link_hostname = urlparse(anchor_element['href']).hostname 
            except:
                # print("this anchor tag has no href! ")
                continue

            if link_hostname and link_hostname != page_hostname:
                # provjera za slucaj da jedna verzija pocinje s www., a druga ne
                if link_hostname.startswith("www.") and not page_hostname.startswith("www."):
                    if link_hostname[4:] == page_hostname:
                        continue
                elif not link_hostname.startswith("www.") and page_hostname.startswith("www."):
                    if link_hostname == page_hostname[4:]:
                        continue
                
                #mozda ce raditi? problem jer nekad nepravilni a tagovi pokupe cijelu stranicu
                if len(list(anchor_element.descendants)) > 5: #arbitraran broj - kako odrediti koliki je broj najbolji?
                    continue

                ext_link = anchor_element.extract()
                # external_links.append(str(ext_link)) #promijeniti sto se appenda, samo tekst ili citav <a> tag
                external_links.append(ext_link)
            else:
                pass
                # i_link = link['href']
                # self.logger.info(f'found internal link: {i_link}')
                # internal_links.append(link['href'])

                # problemi:
                # - ovo uhvati i neke vanjske linkove?
                # - unutarnji linkovi su relativni, nemaju kompletan url -> koristiti LinkExtractor
        
        try:
            page_content = [s for s in soup.body.stripped_strings]
        except:
            page_content = "empty"
        for internal_link in internal_links:
            request = scrapy.Request(
                url=internal_link, 
                callback=self.parse_additional_page, 
                cb_kwargs=dict(main_url = response.url)
            )
            request.cb_kwargs['page_content'] = None
            request.cb_kwargs['external_links'] = external_links
            yield request

        # my_item = UnprocessedSiteContent()
        my_item = ProcessedSiteContent()
        my_item['homepage_url'] = page_url
        if not page_content:
            my_item['page_content'] = "empty"#page_content
        else:
            my_item['page_content'] = page_content
        my_item['external_links'] = external_links
        my_item['site_category'] = category
        my_item['external_links_text'] = "empty"
        yield my_item

        """yield {
            'found text': page_content[:20],
            'found external links': external_links,
            'site_category': category,
        }"""

    def parse_additional_page(self, response, main_url, page_content, external_links):
        self.logger.info(f"Parsing additional page: {response.url}")
        pass





    

    