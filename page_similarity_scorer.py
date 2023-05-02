from urllib.parse import urlparse
import re
from bs4 import BeautifulSoup
import requests
from requests.exceptions import RequestException
import numpy as np

import logging
import argparse

import classla
import joblib

def extract_external_links(soup, page_hostname):
    """function accepts BeautifulSoup object and hostname of page on which outbound links are located,
         extracts external links (modifies soup) and returns them as list
    """
    external_links = []
    for anchor_element in soup.find_all('a'):
        if "rel" in anchor_element.attrs and anchor_element.attrs["rel"] == "nofollow":
            print("> this anchor element has rel=nofollow")
            continue

        link_hostname = None
        href = anchor_element.get('href')
        if href and re.match("(^http://)|(^https://)", href):
            link_hostname = urlparse(href).hostname 
        else:
            continue

        # TODO: STAVITI OBA U LOWERCASE PRIJE USPOREDBE
        # TAKOĐER PROVJERITI JE LI PAGE HOSTNAME SADRŽAN U LINK HOSTNAMEU (ALI PRVO UKLONITI WWW S PAGE HOSTNAMEA)
        if link_hostname and link_hostname != page_hostname:
            # provjera za slucaj da jedna verzija pocinje s www., a druga ne
            if link_hostname.startswith("www.") and not page_hostname.startswith("www."):
                if link_hostname[4:] == page_hostname:
                    continue
            elif not link_hostname.startswith("www.") and page_hostname.startswith("www."):
                if link_hostname == page_hostname[4:]:
                    continue
            
            #nekad nepravilni <a> tagovi pokupe cijelu stranicu, ne uzimati prevelike <a> elemente
            if len(list(anchor_element.descendants)) > 5: #arbitraran broj - kako odrediti koliki je broj najbolji?
                continue

            ext_link = anchor_element.extract()
            if ext_link:
                external_links.append(ext_link)
    return external_links


def get_text_from_body(body_soup, nlp):
    """function receives html body element as soup and parses visible text from it,
         returns page text as string
    """
    page_strings = [s for s in body_soup.stripped_strings]

    cleaned_content = []
    for line in page_strings:
        cleaned_line = "".join(char if char.isalnum() else " " for char in line).split()
        if cleaned_line:
            cleaned_content += [token for token in cleaned_line if token and not token.isspace()]
    if len(cleaned_content) > 500:
        cleaned_content = cleaned_content[:500]

    unlemmatized_text = " ".join(cleaned_content)
    if not unlemmatized_text or unlemmatized_text.isspace():
        return ""
    doc = nlp(" ".join(cleaned_content))
    tokens = doc.to_conll()
    tokens_list = []
    for line in tokens.splitlines():
        if line and not line.startswith("#"):
            token = line.split()[2]
            if token.isalpha(): # vazan korak, iskljucuje se sve sto ima znakove osim slova
                tokens_list.append(token)
    return " ".join(tokens_list)

def parse_txtfile(file_path):
    with open(file_path, "rt", encoding="utf8") as textfile:
        return [line.rstrip("\n") for line in textfile.readlines()]


headers = {
    'user-agent': 'hidden link detection -- thesis (nikola.petrovic@fer.hr)',
    'accept': 'text/html',
}

default_whitelist = [
    "twitter.com", "t.co",
    "www.instagram.com", "instagram.com", 
    "www.facebook.com", "web.facebook.com", "facebook.com",
    "youtu.be", "www.youtube.com", 
    "www.tiktok.com",
    "wordpress.org", "hr.wordpress.org",
    "itunes.apple.com",
    "play.google.com", "drive.google.com", "www.google.com", "maps.google.com", "plus.google.com",
    "forms.gle",
    "www.flickr.com", "www.linkedin.com",
    "www.pinterest.com",
]

def main():
    #konfiguriraj logger
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', 
        # filename='example.log', 
        # encoding='utf-8',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO
    )

    logging.info("* starting up Malicious Links Detector...")
    parser = argparse.ArgumentParser(description="Determine maliciousness of external links on one or more webpages.")
    parser.add_argument("--url", help="URL of page to be analyzed for malicious links")
    parser.add_argument("--from_file", help="path to txt file in which URLs to analyize are separated by newline")
    parser.add_argument("--pipeline", help="path to joblib file")
    parser.add_argument("--whitelist", help="path to txt file in which whitelisted URLs are separated by newline")
    parser.add_argument("--threshold", help="number between 0 and 1")

    args = parser.parse_args()

    if args.url:
        pass

    # učitaj pipeline
    if args.pipeline:
        pipe = joblib.load(args.pipeline)
    else:
        pipe = joblib.load("./wwwhr-to-tfidf-pipeline.joblib")

    # učitaj whitelist
    if args.whitelist:
        whitelist_sites = parse_txtfile(args.whitelist)
    else:
        whitelist_sites = default_whitelist

    # učitaj threshold
    # anchor_similarity_threshold = 0.1
    similarity_threshold = 0.1
    if args.threshold:
        similarity_threshold = float(args.threshold)
    if similarity_threshold < 0 or similarity_threshold > 1:
        logging.error("similarity threshold must be between 0 and 1!")
        exit()
    
    #učitaj modele potrebne za lematizaciju teksta
    nlp = classla.Pipeline('hr', processors='tokenize,pos,lemma')


    ### UVESTI HTML KODOVE + URLOVE POVUCENE IY MONGODB BAZE
    ### OVO JE SAMO PLACEHOLDER URL
    url1 = "https://quotes.toscrape.com/page/1/"
    
    for site in [url1]:
        logging.info(f"*** checking page {site} for external links...")

        html = None

        soup = BeautifulSoup(html, 'html.parser')
        if soup is None or not soup:
            logging.info("* Website cannot be parsed for external links")
            continue

        # finding external links and extracting them from page
        external_links = extract_external_links(soup, page_hostname=urlparse(site).hostname)
        if len(external_links) > 100:
            logging.warning("- this site has an unusually large amount of outbound links.")
            continue
        else:
            logging.info(f"* found {len(external_links)} external links on page")

        # getting text from page and vectorizing it
        page_content = get_text_from_body(soup.body, nlp)
        content_tfidf = pipe.transform([page_content])


        #testing external links
        for i, ext_link in enumerate(external_links):
            a_soup = ext_link
            logging.info(f"* examining external link {i+1}...")

            #getting anchor text or alt text from link
            if a_soup.string is None:
                try:
                    alt_text = a_soup.img.get("alt")
                    if alt_text:
                        anchor_text = str(alt_text)
                    else:
                        anchor_text = "None"
                except:
                    anchor_text = "None"
            else:
                anchor_text = str(a_soup.string).strip()

            #rule-based filtering of links that are highly unlikely to be spam
            if "rel" in a_soup.attrs: # PRETPOSTAVKA: SPAM LINKOVI NEMAJU REL ATRIBUT
                # logging.info(f"* {anchor_text} --- anchor element has rel attribute -- uncommon for spam...")
                logging.info("* anchor element has rel attribute, uncommon for spam; ignoring link.")
                continue
            if anchor_text.lower().strip() == "none" or anchor_text.lower().strip() == "image":
                logging.info("* missing or generic anchor text; ignoring link...")
                continue
            if urlparse(a_soup.get('href')).hostname in whitelist_sites:
                logging.info("+ outbound link leads to whitelisted site")
                continue

            #checking cosine similarity between anchor text and host/tested/our page
            anchor_tfidf = pipe.transform([anchor_text])
            anchor_cosine = np.dot(content_tfidf.toarray().flatten(), anchor_tfidf.toarray().flatten())
            if anchor_cosine > similarity_threshold:
                # logging.info(f"+ {anchor_text} --- OK: anchor text shows similarity to page")
                logging.info("+ OK: anchor text shows similarity to page")
                continue

            #checking cosine similarity between host/tested/our page and page that outbound link leads to
            a_url = a_soup.get('href')
            try:
                logging.info(f"* visiting outbound link... page: {a_url}, anchor text: {anchor_text}")

                r_head = requests.head(a_url, headers=headers, allow_redirects=True, timeout=3)
                length = r_head.headers.get('Content-Length')
                #ovdje se može dodati i provjera content typea, tj. radi li se o html/text contentu
                # https://almanac.httparchive.org/en/2020/page-weight
                if length and int(length) > 1024*1024*10: #ako je duljina contenta veca od 10 megabajta
                    logging.warning("* webpage too big -- ignoring...")
                    continue

                resp = requests.get(a_url, headers=headers, timeout=3)
                if resp.status_code != requests.codes.ok:
                    logging.warning("- response was not successful!")
                    continue
                if "text/html" not in resp.headers['Content-Type']:
                    logging.warning(f"* response Content-Type is not text/html, it is {resp.headers['Content-Type']} ...")
                    continue
                soup = BeautifulSoup(resp.text, 'html.parser').body
                if soup is None or not soup:
                    raise Exception()
            except RequestException as e:
                logging.warning(f"* RequestException was raised: {str(e)}")
                continue
            except Exception:
                logging.warning("* site has no parseable content")
                continue

            visited_content = get_text_from_body(soup, nlp)
            visited_content_tfidf = pipe.transform([visited_content])

            # print(page_content)
            # print("-"*20)
            # if not visited_content or visited_content.isspace():
            #     print("*** visited page has no readable content")
            # else:
            #     print(visited_content)
            # print("-"*20)
            pages_cosine = np.dot(content_tfidf.toarray().flatten(), visited_content_tfidf.toarray().flatten())
            logging.info(f"* pages cosine similarity: {pages_cosine}, threshold: {similarity_threshold}")
            if pages_cosine < similarity_threshold:
                logging.warning("- similarity between tested page and visited page is below threshold!")
            else:
                logging.info("+ OK: visited page has enough similarity to tested page")
        print()

if __name__ == "__main__":
    main()
