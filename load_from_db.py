from io import StringIO
from sshtunnel import SSHTunnelForwarder
import pymongo
import logging
from threading import Thread
from time import time, sleep
# import classla
import joblib
from random import uniform
from bson.objectid import ObjectId
from pprint import pprint

import page_process_util as ppu

MY_LOG_NAME = "websecradar_test_log.json"

def perform_queries(db, pipe):
    with open("./tmp/last_seen_id.txt", "r") as f:
        ### prvi ID ... ObjectId('603a6c5139ec133a07a37e2b')
        last_seen_id = ObjectId(f.readline().strip())
        # last_seen_id = ObjectId('603a6c5139ec133a07a37e2b')
    try:
        pages_coll = db['crawled_data_pages_v0']
        urls_coll = db['crawled_data_urls_v0']
        
        # PROMIJENI STEP I END_OF_RANGE
        step = 1000
        end_of_range = 100000 # urls_coll.estimated_document_count()
        for i in range(0, end_of_range, step):
        
            hashes_dict = {}

            for url_doc in urls_coll.find({
                    "_id": { "$gt": last_seen_id }, "checks.status": "ok" 
                }, {
                    "_id": 1, "url": 1, "last_check": 1, "lastfetch": 1,
                    "checks": {
                        "$slice": [ # https://stackoverflow.com/questions/36126289/how-to-slice-a-filter-result-in-mongodb
                            {"$filter": {
                                "input": "$checks",
                                "as": "check",
                                "cond": { "$eq": ["$$check.status", "ok"]}
                            }},
                            -1,
                        ]
                    }
                }).sort("_id", pymongo.ASCENDING).limit(step):
                headers = url_doc['checks'][0]['headers']
                if 'Content-Type' in headers and 'text/html' in headers['Content-Type']:
                    hash = url_doc['checks'][0]['hash']
                    hashes_dict[hash] = url_doc['url']
                last_seen_id_unparsed = url_doc['_id']
            
            threads = [] # https://www.shanelynn.ie/using-python-threading-for-multiple-results-queue/
            log_buffer = StringIO()
            for page in pages_coll.find({'hash': {"$in": list(hashes_dict.keys())}}):
                h = page['hash']
                # thread = Thread(target=ppu.page_info_to_json, args=(hashes_dict[h], h, page['page'], pipe, log_buffer, ))
                thread = Thread(target=ppu.look_for_red_flags, args=(hashes_dict[h], h, page['page'], pipe, log_buffer, ))
                thread.start()
                threads.append(thread)
            for t in threads:
                t.join()
            with open("./tmp/"+MY_LOG_NAME, "a") as txtlog:
                print(log_buffer.getvalue(), file=txtlog) # print(log_buffer.getvalue()+",", file=txtlog)
                log_buffer.close()

            last_seen_id = last_seen_id_unparsed # provjeriti kad pohraniti last_seen_id
            sleep(uniform(0.5, 1.5))
            logging.debug("sleeping...")
    except Exception as e:
        logging.error(e)
    finally:
        pass
        with open("./tmp/last_seen_id.txt", "w") as f:
            f.write(str(last_seen_id))
    return

def main():

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)-12s %(levelname)s | %(message)s')
    # logging.debug("going to load nlp pipeline now...")
    # pipe = joblib.load("./wwwhr-to-tfidf-pipeline.joblib")
    pipe = None

    # CREDS = dict.fromkeys(["USER", "SSH_PW", "MONGO_HOST", "MONGO_DB", "MONGO_PW"])
    with open(".env") as env:
        env_lines = env.readlines()
        USER=env_lines[0].split("=")[1].strip()
        SSH_PW=env_lines[1].split("=",1)[1].strip()
        MONGO_HOST=env_lines[2].split("=",1)[1].strip()
        MONGO_DB=env_lines[3].split("=",1)[1].strip()
        MONGO_PW=env_lines[4].split("=",1)[1].strip()

    server = SSHTunnelForwarder( # https://stackoverflow.com/a/42763361
        (MONGO_HOST, 10004),
        ssh_username=USER,
        ssh_password=SSH_PW,
        remote_bind_address=('127.0.0.1', 27017),
        local_bind_address=('127.0.0.1', 27017)
    )

    try:
        server.start()
        logging.debug("going to establish connection to database now...")
        client = pymongo.MongoClient("mongodb://127.0.0.1:27017",
            username=USER,
            password=MONGO_PW,
            authSource='admin',
            authMechanism='SCRAM-SHA-1'
        )
        logging.info("starting timekeeping now...")
        t0 = time()
        db = client[MONGO_DB]
            
        while(True):
            perform_queries(db, pipe)
            logging.info(f"elapsed time for database operations: {time() - t0} seconds")
            logging.debug("sleeping for 5 seconds")
            sleep(5)
    except KeyboardInterrupt:
        print("Database traversal interrupted via keyboard. Going to end program...")
    except Exception as e:
        logging.error(e)
    finally:
        client.close()
        server.stop()

if __name__ == "__main__":
    main()
