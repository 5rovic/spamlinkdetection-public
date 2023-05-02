import argparse
import subprocess

from time import time
from urllib.parse import urlparse

def run_subprocesses(my_url):
    t1 = time()
    p1 = subprocess.run(["python", "./pagescraper.py", my_url])
    print(p1)
    p2 = subprocess.run(["python", "./tokengetter.py"])
    print(p2)
    p3 = subprocess.run(["python", "./similaritygrader.py", my_url])
    print(p3)
    print(f"LINKJUDGE INFO: analyzed site {my_url} in {time()-t1} seconds")

def check_url(url): # https://stackoverflow.com/a/52455972
    try:
        res = urlparse(url)
        # if res.hostname.split(".")[-1] != "hr":
        #     print("stranica bi trebala bit iz hr domene")
        # print(res.scheme, res.netloc)
        return all([res.scheme, res.netloc])
        # return False
    except:
        print("something is wrong with the url")
        return False

def main():
    parser = argparse.ArgumentParser(description="Determine maliciousness of external links on one or more webpages.")
    parser.add_argument("--from_url")
    parser.add_argument("--from_file")

    args = parser.parse_args()

    if args.from_url:
        my_url = args.from_url
        if check_url(my_url):
            run_subprocesses(my_url)
    elif args.from_file:
        my_path = args.from_file
        with open(my_path, "r") as urls_file:
            urls = [line.split()[1] for line in urls_file.readlines()]
        t0 = time()
        for my_url in urls:
            run_subprocesses(my_url)
        print(f"LINKJUDGE INFO: linkjudge is done in {time()-t0} seconds.")
    else:
        print("--from_file or --from_url argument must be entered")

if __name__ == "__main__":
    main()
    