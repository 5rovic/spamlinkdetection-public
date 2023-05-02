import sys
import xml.etree.ElementTree as ET

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.pipeline import make_pipeline

import joblib

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

def collect_documents(xml_file):
  tree = ET.parse(xml_file)
  root = tree.getroot()
  my_docs = []
  cat_labels = []

  for website in root.findall('website'):
      try:
          content = website.find('page_content').text 
          cat = website.find('site_category').text.split("_", 1)[0]
      except:
          print(f"caught exception")
          continue
      my_docs.append(content)
      cat_labels.append(cat)

  return my_docs, cat_labels

def main():

    # putanja do direktorija iz kojeg ce se ucitavati dataset
    path_to_set = sys.argv[1]

    X = []
    y = []
    for kat in katalog_categories:
        xml_path = f"{path_to_set}/processed-wwwhr-{kat}.xml"

        small_X, small_y = collect_documents(xml_path)
        X += small_X
        y += small_y

    vectorizer = CountVectorizer(
        max_df=0.5, #0.95 
        ngram_range=(1,2), #(1,1)
        max_features=50000,
        stop_words = None 
    )
    transformer = TfidfTransformer(use_idf=True)
    pipe = make_pipeline(vectorizer, transformer, verbose=True)

    pipe.fit(X)

    joblib.dump(pipe, "./wwwhr-to-tfidf-pipeline.joblib") 

if __name__ == "__main__":
    main()