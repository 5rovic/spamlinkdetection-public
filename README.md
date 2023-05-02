# spam link detection

## Potrebne knjižnice (Dependencies)
Da bi sustav za detekciju funkcionirao, potrebno je instalirati sljedeće knjižnice za programski jezik Python:

* `Scrapy` 
* `Scikit-learn`
* `BeautifulSoup`
* `tqdm`
* `CLASSLA`
* `jusText` -- više nije potrebna
* `requests`
* `joblib`

## Prije prvog pokretanja sustava za detekciju
Potrebno je pokrenuti `classla-model-downloader.py` skriptu za preuzimanje CLASSLA modela za procesiranje standardnog hrvatskog jezika. 

Pokrenuti `model-trainer.py` skriptu kojoj se u naredbenom retku kao argument daje putanja do direktorija u kojoj se nalazi dataset procesiranih stranica. 

## Pokretanje page-similarity-scorer.py skripte
Kao argument u naredbenom retku potrebno je dodati url stranice koja se pregledava.
```cmd
python page-similarity-scorer.py --url [URL]
```
Za ispis svih argumenata upisati u naredbeni redak:
```cmd
python page-similarity-scorer.py --help
```

## page-similarity-scorer-tofile.py skripta
Ova skripta služila je samo za testiranje sustava na stranicama iz www.hr kataloga.

## Katalogsites spider
U ovome projektu nalazi se Scrapy projekt za web-pauka koji otvara XML datoteke s URL-ovima uz www.hr kataloga
i posjećuje te URL-ove te preuzima tekst i vanjske poveznice s posjećenih stranica.

### Napomene
Preporučuje se alat pokretati unutar virtualnog okruženja.
