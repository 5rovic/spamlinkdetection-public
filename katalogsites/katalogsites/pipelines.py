# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from scrapy.exporters import XmlItemExporter

import classla

class KatalogsitesPipeline:

    def open_spider(self, spider):
        self.nlp = classla.Pipeline('hr', processors='tokenize,pos,lemma')

    def close_spider(self, spider):
        print("KatalogsitesPipeline is done lemmatizing page content.")

    def has_text(self, anchor_tag_soup):
        has_text = False
        if anchor_tag_soup.string is None:
            try:
                alt_text = anchor_tag_soup.img.get("alt")
                if alt_text and not alt_text.isspace(): 
                    has_text = True
            except:
                pass
        elif not anchor_tag_soup.string.isspace():
            has_text = True
        return has_text
    
    def get_text(self, anchor_tag_soup):
        if anchor_tag_soup.string is None:
            try:
                alt_text = anchor_tag_soup.img.get("alt")
                if alt_text:
                    anchor_text = str(alt_text)
                else:
                    anchor_text = "None"
            except:
                anchor_text = "None"
        else:
            anchor_text = str(anchor_tag_soup.string)

        if not anchor_text.isspace() and anchor_text.split()[0].isalpha(): #prepraviti ovo
            doc = self.nlp(anchor_text)
            tokens = doc.to_conll()
            lemmatized_text = []
            for line in tokens.splitlines():
                if line and not line.startswith("#"):
                    if len(line) > 2:
                        token = line.split()[2]    
                        if token.isalpha():
                            lemmatized_text.append(token)
            lemmatized_anchor_text = " ".join(lemmatized_text)
        else:
            lemmatized_anchor_text = anchor_text
        return lemmatized_anchor_text

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if adapter.get('page_content'):
            page_strings = adapter['page_content']
            joined_paragraphs = " ".join(page_strings) 
            doc = self.nlp(joined_paragraphs)
            tokens = doc.to_conll()

            tokens_list = []
            for line in tokens.splitlines():
                if line and not line.startswith("#"):
                    token = line.split()[2]
                    if token.isalpha(): # vazan korak, iskljucuje se sve sto ima znakove osim slova
                        tokens_list.append(token)

            # smanjujem kolicinu teksta jer neke stranice imaju previse sadrzaja, 
            # a sto je sadrzaj nize na stranici, vjerojatno je manje bitan
            if len(tokens_list) > 500:
                tokens_list = tokens_list[:500]

            if tokens_list:            
                adapter['page_content'] = " ".join(tokens_list)
            else:
                # adapter['page_content'] = "empty"
                raise DropItem(f"missing content in {adapter['homepage_url']}")
            ext_links = adapter['external_links']

            # if not tokens_list or not ext_links:
            #     # raise DropItem(f"missing content in {item}")
            #     raise DropItem(f"missing content in {adapter['homepage_url']}")

            # pruned_ext_links = [str(e) for e in ext_links if self.has_text(e)]

            pruned_ext_links = [e for e in ext_links if self.has_text(e)]
            # ext_links_text = [self.get_text(e) for e in pruned_ext_links]
            
            ext_links_dict = dict.fromkeys(range(len(pruned_ext_links)))
            for i, e in enumerate(pruned_ext_links):
                ext_links_dict[i] = self.get_text(e)
            adapter['external_links'] = [str(i)+": "+" ".join(str(e).split()) for i, e in enumerate(pruned_ext_links)]
            adapter['external_links_text'] = [str(key)+": "+ext_links_dict[key] for key in ext_links_dict.keys()]
        return item

class PerCategoryExportPipeline:
    """Save processed .hr domain websites from www.hr catalogue to different XML files according to website category"""
    
    def open_spider(self, spider):
        self.category_to_exporter = {}

    def close_spider(self, spider):
        for exporter, xml_file in self.category_to_exporter.values():
            exporter.finish_exporting()
            xml_file.close()

    def _exporter_for_item(self, item):
        adapter = ItemAdapter(item)

        category = adapter['site_category'].split("_", 1)[0]
        
        if category not in self.category_to_exporter:

            xml_file = open(f'E:/wwwhr katalog/processed wwwhr2/processed-wwwhr2-{category}.xml', 'wb')

            exporter = XmlItemExporter(xml_file, item_element='website', root_element='root')
            exporter.start_exporting()
            self.category_to_exporter[category] = (exporter, xml_file)

        return self.category_to_exporter[category][0]

    def process_item(self, item, spider):
        exporter = self._exporter_for_item(item)
        exporter.export_item(item)
        return item
