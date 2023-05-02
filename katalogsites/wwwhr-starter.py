import subprocess

def main():
    """wwwhr scrapy subprocess starter"""
    katalog_categories = [
        'abouthr',
        'education',
        'entert',
        'events',
        'news',
        'organiz',
        'politics',
        'science',
        'society',
        'sports',
        'arts',
        'tour',
        'computers',
        'business',
    ]
    for category in katalog_categories:
        print(f"---scraping category {category} ---")
        xml_fullpath = rf"E:\wwwhr katalog\wwwhr-{category}.xml"
        p1 = subprocess.run(["scrapy", "crawl", "hrsites", "-a", "xml_path="+xml_fullpath])
        print(p1)
            
if __name__=="__main__":
    main()