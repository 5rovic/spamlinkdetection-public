import pprint
from bs4 import BeautifulSoup
from page_similarity_scorer import extract_external_links, get_text_from_body
from urllib.parse import urlparse
import logging
import numpy as np
import requests
from requests.exceptions import RequestException
import tldextract

import stemmer.edited_stemmer

import json
import joblib

headers = {
    'user-agent': 'spam link detection -- nikola.petrovic@fer.hr',
    'accept': 'text/html',
}

with open('./tmp/whitelist.txt', 'r') as list:
    whitelist = [line for line in list.read().splitlines()]
with open('./tmp/wwwhr_whitelist.txt', 'r') as list:
    whitelist2 = [line for line in list.read().splitlines()]
wwwhr_whitelist = set(whitelist2)
similarity_threshold = 0.1

## deprecated -- PREGLEDATI PA OBRISATI
def look_for_spam_links(url, html, nlp, pipe, txtlog):
    notes = []
    soup = BeautifulSoup(html, 'html.parser')
    if soup is None or not soup:
        logging.info(f"* Webpage {url} cannot be parsed for external links")
        return

    external_links = extract_external_links(soup, page_hostname=urlparse(url).hostname)
    if len(external_links) > 100:
        notes.append("- this page has an unusually large amount of outbound links.")
        return notes
    elif len(external_links) < 1:
        notes.append(f"* found no external links on page")
        return notes
    else:
        notes.append(f"* found {len(external_links)} external links on page")
        
    ### getting text from page and vectorizing it
    # page_content = get_text_from_body(soup, nlp)
    page_content = stem_body(soup)
    content_tfidf = pipe.transform([page_content])

    #testing external links
    for i, ext_link in enumerate(external_links):
        a_soup = ext_link
        notes.append(f"* examining external link {i+1}...")

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
            notes.append("* anchor element has rel attribute, uncommon for spam; ignoring link.")
            continue
        if anchor_text.lower().strip() == "none" or anchor_text.lower().strip() == "image":
            notes.append("* missing or generic anchor text; ignoring link...")
            continue
        
        #checking cosine similarity between anchor text and host/tested/our page
        anchor_tfidf = pipe.transform([anchor_text])
        anchor_cosine = np.dot(content_tfidf.toarray().flatten(), anchor_tfidf.toarray().flatten())
        if anchor_cosine > similarity_threshold:
            notes.append("+ OK: anchor text shows similarity to page")
            continue

        #checking cosine similarity between host/tested/our page and page that outbound link leads to
        a_url = a_soup.get('href')
        try:
            notes.append(f"* visiting outbound link... page: {a_url}, anchor text: {anchor_text}")

            r_head = requests.head(a_url, headers=headers, allow_redirects=True, timeout=3)
            length = r_head.headers.get('Content-Length')
            #ovdje se može dodati i provjera content typea, tj. radi li se o html/text contentu
            # ZAR SE TO NE FILTRIRA CUSTOM REQUEST HEADEROM

            # https://almanac.httparchive.org/en/2020/page-weight
            if length and int(length) > 1024*1024*10: #ako je duljina contenta veca od 10 megabajta
                notes.append("* webpage too big -- ignoring...")
                continue

            resp = requests.get(a_url, headers=headers, timeout=3)
            if resp.status_code != requests.codes.ok:
                notes.append("- response was not successful!")
                continue
            if "text/html" not in resp.headers['Content-Type']:
                notes.append(f"* response Content-Type is not text/html, it is {resp.headers['Content-Type']} ...")
                continue
            soup = BeautifulSoup(resp.text, 'html.parser').body
            if soup is None or not soup:
                raise Exception()
        except RequestException as e:
            notes.append(f"* RequestException was raised: {str(e)}")
            continue
        except Exception:
            notes.append("* site has no parseable content")
            continue

        # visited_content = get_text_from_body(soup, nlp)
        visited_content = stem_body(soup)
        visited_content_tfidf = pipe.transform([visited_content])

        pages_cosine = np.dot(content_tfidf.toarray().flatten(), visited_content_tfidf.toarray().flatten())
        notes.append(f"* pages cosine similarity: {pages_cosine}, threshold: {similarity_threshold}")
        if pages_cosine < similarity_threshold:
            notes.append("- similarity between tested page and visited page is below threshold!")
        else:
            notes.append("+ OK: visited page has enough similarity to tested page")
    notes.append("")
    # print('\n'.join(notes))
    txtlog.writelines(notes)

def check_urls_overlap(this_url, other_url):
    ### PROBATI TLDEXTRACT S include_psl_private_domains=True I ISKLJUCENOM GLOBALNOM WHITELISTOM
    subdomain1, domain1, suffix1 = tldextract.extract(urlparse(this_url).hostname)
    subdomain2, domain2, suffix2 = tldextract.extract(urlparse(other_url).hostname)
    if domain1 == domain2:
        overlap = True
    elif (domain1 != domain2) and (domain1 in subdomain2.split(".") or domain2 in subdomain1.split(".")):
        overlap = True
    else:
        overlap = False
    return overlap
    

    
def stem_body(body_soup):
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
    
    tokens = stemmer.edited_stemmer.stem(unlemmatized_text)
    # tokens_list = []
    # for token in tokens:
    #     if token.isalpha(): # vazan korak, iskljucuje se sve sto ima znakove osim slova
    #         tokens_list.append(token)
    # return " ".join(tokens_list)
    return " ".join(tokens)

def page_info_to_json(url, hash, html, pipe, txtlog):
    notes = dict.fromkeys(["url", "hash", "parseable"])
    indent = 2
    notes['url'] = url
    notes['hash'] = hash

    soup = BeautifulSoup(html, 'html.parser')
    if soup is None or not soup:
        notes['parseable'] = "no"
        # return json.dumps(notes, indent=indent)
        txtlog.writelines(json.dumps(notes, indent=indent)+",")
        return
    else:
        notes['parseable'] = "yes"
    
    external_links = extract_external_links(soup, page_hostname=urlparse(url).hostname)
    num_ext_links = len(external_links)
    notes['num_ext_links'] = num_ext_links
    if num_ext_links > 100 or num_ext_links < 1:
        # return json.dumps(notes, indent=indent)
        txtlog.writelines(json.dumps(notes, indent=indent)+",")
        return
    
    ### getting text from page and vectorizing it
    page_content = stem_body(soup)
    content_tfidf = pipe.transform([page_content])

    ext_link_notes = []
    #testing external links
    for ext_link in external_links:
        ext_link_note = dict.fromkeys(["ext_url", "anchor_text"])
        
        a_soup = ext_link # a_soup == anchor element soup

        a_url = a_soup.get('href')
        ext_link_note['ext_url'] = a_url
        outbound_hostname = urlparse(a_url).hostname
        extract = tldextract.extract(outbound_hostname)
        if (extract.domain in whitelist) or (outbound_hostname in wwwhr_whitelist):
        # if any(whitesite in a_url for whitesite in whitelist):
            ext_link_note['whitelisted'] = 'yes'
            ext_link_notes.append(ext_link_note)
            continue
        # usporedba linka s host urlom
        if check_urls_overlap(url, a_url):
            ext_link_note['overlap'] = 'yes'
            ext_link_notes.append(ext_link_note)
            continue
        ### getting anchor text or alt text from link
        ### ovo se valjda da refaktorirati, msm na sta ovo lici
        if a_soup.string is None:
            try:
                alt_text = a_soup.img.get("alt").lower().strip()
                ext_link_note['alt_text'] = alt_text
                anchor_text = alt_text
            except:
                anchor_text = "None"
        else:
            anchor_text = str(a_soup.string).lower().strip()
            ext_link_note['anchor_text'] = anchor_text

        #rule-based filtering of links that are highly unlikely to be spam
        if "rel" in a_soup.attrs: # PRETPOSTAVKA: SPAM LINKOVI NEMAJU REL ATRIBUT
            ext_link_note['rel'] = a_soup.attrs.get("rel")
            ext_link_notes.append(ext_link_note)
            continue
        if anchor_text == "none" or anchor_text == "image":
            ext_link_notes.append(ext_link_note)
            continue
        
        #checking cosine similarity between anchor text and host/tested/our page
        anchor_tfidf = pipe.transform([anchor_text])
        anchor_cosine = np.dot(content_tfidf.toarray().flatten(), anchor_tfidf.toarray().flatten())
        ext_link_note['anchor_cosine'] = anchor_cosine
        if anchor_cosine > similarity_threshold:
            ext_link_notes.append(ext_link_note)
            continue

        try:
            r_head = requests.head(a_url, headers=headers, allow_redirects=True, timeout=3)
            length = r_head.headers.get('Content-Length')
            #ovdje se može dodati i provjera content typea, tj. radi li se o html/text contentu
            # ZAR SE TO NE FILTRIRA CUSTOM REQUEST HEADEROM

            # https://almanac.httparchive.org/en/2020/page-weight
            if length and int(length) > 1024*1024*10: #ako je duljina contenta veca od 10 megabajta
                ext_link_note['content_length'] = length
                ext_link_notes.append(ext_link_note)
                continue

            resp = requests.get(a_url, headers=headers, timeout=3) # provjeri zasto requests.get zapne kod live.tranzistor.hr stranice na jednom vanjskom linku; problem s headerom?
            if resp.status_code != requests.codes.ok:
                raise Exception()
            if "text/html" not in resp.headers['Content-Type']:
                raise Exception()
            soup = BeautifulSoup(resp.text, 'html.parser').body
            if soup is None or not soup:
                raise Exception()
        except RequestException as e:
            ext_link_note['reachable'] = 'no'
            ext_link_notes.append(ext_link_note)
            continue
        except Exception as e:
            print(e)
            ext_link_note['reachable'] = 'unparseable'
            ext_link_notes.append(ext_link_note)
            continue
        ext_link_note['reachable'] = 'yes'

        # visited_content = get_text_from_body(soup, nlp)
        visited_content = stem_body(soup)
        visited_content_tfidf = pipe.transform([visited_content])
        ext_link_note['visited_cosine'] = np.dot(content_tfidf.toarray().flatten(), visited_content_tfidf.toarray().flatten())
        ext_link_notes.append(ext_link_note)
    notes['ext_links'] = ext_link_notes
    txtlog.writelines(json.dumps(notes, indent=indent)+",")
    # return json.dumps(notes, indent=indent)

def look_for_red_flags(url, hash, html, pipe, txtlog):
    red_flags = ["hidden", "height:1px", "height: 1px", "display:none", "display: none"]
    soup = BeautifulSoup(html, 'html.parser')

    notes = {}
    indent = 2
    notes['url'] = url
    notes['hash'] = hash

    def check_for_red_flags(element_style):
        return any(red_flag in element_style for red_flag in red_flags)
    sus_links = []
    rel_ignore = ["nofollow", "noopener", "noreferrer"]
    for anchor_element in soup.find_all('a'):
        if "href" not in anchor_element.attrs:
            continue
        if "href" in anchor_element.attrs and "http" not in anchor_element.attrs["href"]:
            continue
        if "rel" in anchor_element.attrs and any(ignore in anchor_element.attrs["rel"] for ignore in rel_ignore):
            continue

        if 'style' in anchor_element.attrs:
            if check_for_red_flags(anchor_element['style']):
                sus_links.append(str(anchor_element))
        elif 'style' in anchor_element.parent.attrs:
            if check_for_red_flags(anchor_element.parent['style']):
                sus_links.append(str(anchor_element))
    notes['sus-links'] = sus_links
    if len(sus_links) > 0:
        txtlog.writelines(json.dumps(notes, indent=indent)+",")

def main():
    # pprint.pprint(whitelist)
    url = "http://blog.dnevnik.hr/mladendizajn/"
    # print(get_domain_and_subdomains(url))
    print(check_urls_overlap("http://4.10.dba.skylink.hr", "https://statcounter.com/"))

    with open("./scraped/page-3.html", "r", ) as f:
        html = "".join(f.readlines())
    # j = page_info_to_json("http://knjiznica-losinj.hr/", "hash"*8 , html, joblib.load("./wwwhr-to-tfidf-pipeline.joblib"))
    # print(j)  
    # soup = BeautifulSoup(html, 'html.parser')  
    # print('\n'.join([s for s in soup.stripped_strings]))

if __name__ == "__main__":
    main()