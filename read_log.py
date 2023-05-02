import json
from pprint import pprint
import glob
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import whois

THRESHOLD = 0.2

def create_wwwwhr_whitelist():
    all_files = glob.glob("E:\wwwhr katalog\*.xml")

    for file in all_files:
        print(file)
        tree = ET.parse(file)
        root = tree.getroot()
        for website in root:
            single_cat_urls = []
            hostname = urlparse(website[1].text.strip()).hostname
            single_cat_urls.append(hostname + "\n")
            with open("./tmp/wwwhr_whitelist.txt", "a", encoding="utf-8") as wl:
                wl.writelines(single_cat_urls)

def remove_wwwhr_whitelist_duplicates():
    with open("./tmp/wwwhr_whitelist.txt", "w", encoding="utf-8") as outfile, open("./tmp/wwwhr_whitelist_w_duplicates.txt", "r", encoding="utf-8") as infile:
        seen_lines = set()
        for line in infile:
            if line not in seen_lines:
              outfile.write(line)
              seen_lines.add(line)

def load_docs(my_file):
    with open(my_file, "r") as f:
        pages_array = json.load(f)
    if pages_array:
        return pages_array
    return None

def test_whois():
    my_url = "http://www.knjigice.com/"
    domain = urlparse(my_url).hostname
    w = whois.whois(domain)
    print(w.text)
    
def main():
    # mal_urls = set()
    hashes_set = set()
    pages = []
    pages_array1 = load_docs(r"C:\Users\Nikola\Documents\1 Sem1\tmp\found_mal_urls.json")
    for page in pages_array1:
        # for link in page['suspicious-links']:
        #     mal_urls.add(link)
        if page['hash'] not in hashes_set:
            hashes_set.add(page['hash'])
            pages.append(json.dumps(page, indent=2)+",")
    pages_array2 = load_docs(r".\tmp\websecradar_all_hidden.json")
    # total_links_count = 0
    for page in pages_array2:
        # for link in page['sus-links']:
        #     mal_urls.add(link)
        if page['hash'] not in hashes_set:
            hashes_set.add(page['hash'])
            pages.append(json.dumps(page, indent=2)+",")

    # svi = json.dumps(pages)
    with open(r"C:\Users\Nikola\Documents\1 Sem1\sumnjivi_linkovi.json", "w") as jf:
        for p in pages:
            print(p, end="", file=jf)
        # json.dump(svi, jf)

    # for page in pages_array:
    #     no_of_links = len(page['suspicious-links'])
    #     # print(f"site: {page['url']}, \n\tspam links count: {no_of_links}")
    #     total_links_count += no_of_links
    # print("this many infected pages:", len(pages_array))
    # print("this many malicious urls (with duplicates):", total_links_count)
    # print("this many unique suspicious urls:", len(mal_urls) )

if __name__ == "__main__":
    main()

# for page in pages_array:
#     if page['num_ext_links'] > 0:
#         print(f"page {page['url']} has {page['num_ext_links']} external links") 

# useful_pages_array = [obj for obj in pages_array if (obj['num_ext_links'] > 0)]
# print(len(useful_pages_array)) # 4743

# to_examine_count = 0
# for page in useful_pages_array:
#     if page['num_ext_links'] > 100:
#         continue
#     try:
#         alert = False
#         for ext_link in page['ext_links']:
#             if "anchor_cosine" in ext_link and ext_link["anchor_cosine"] < THRESHOLD:
#                 if 'reachable' in ext_link and ext_link['reachable'] == 'yes' and ext_link['visited_cosine'] < THRESHOLD:
#                     print(f"{page['url']} ___ {ext_link['ext_url']} ___ {ext_link['visited_cosine']}")
#                 alert = True
#         if alert:
#             to_examine_count += 1
#             # pprint(page)
#     except:
#         print("--------- some error because of page below")
#         pprint(page)
#         break
# print(to_examine_count)

"""
50832 stranica dohvacenih iz baze
4743 stranice imaju eksterne linkove
3849 stranica sadrzi link ciji je anchor cosine manji od 0.1

Dakle, samo oko 10% stranica ima sadrzaj koji mogu analizirati? 
Pretpostavka na temelju broja stranica s eksternim linkovima, 
iako sigurno ima stranica tipa text/html koje nemaju eksterne linkove
"""
