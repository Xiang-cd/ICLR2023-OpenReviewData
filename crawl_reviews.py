import os
import time
import threading
import IPython
import pandas as pd
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

df = pd.read_csv('paperlist23.tsv', sep='\t', index_col=0)
num_of_workers = 8
total_len = len(list(df.link.items()))
segment = (total_len // num_of_workers) + 1

def retry(dr, time, cond, maxtime):
    dr.refresh()
    try:
        WebDriverWait(dr, time).until(cond)
    except:
        retry(dr, 10, cond, maxtime-1)




class Worker(threading.Thread):
    def __init__(self, link_list, start_index, end_index):
        super(Worker, self).__init__()
        self.link_list = link_list
        self.start_index = start_index
        self.end_index = end_index
        self.ratings = dict()
        self.decisions = dict()
        self.dr = webdriver.Chrome()

    def run(self):
        for paper_id, link in tqdm(self.link_list[self.start_index:self.end_index]):
            try:
                self.dr.get(link)
                xpath = '//div[@id="note_children"]//span[@class="note_content_value"]/..'
                cond = EC.presence_of_element_located((By.XPATH, xpath))
                try:
                    WebDriverWait(self.dr, 10).until(cond)
                except:
                    retry(self.dr, 10, cond, 3)
                elems = self.dr.find_elements(By.XPATH, xpath)
                assert len(elems), 'empty ratings'
                self.ratings[paper_id] = pd.Series([
                    int(x.text.split(': ')[1]) for x in elems if x.text.startswith('Recommendation:')
                ], dtype=int)
                # decision = [x.text.split(': ')[1] for x in elems if x.text.startswith('Decision:')]
                # self.decisions[paper_id] = decision[0] if decision else 'Unknown'
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(paper_id, e)
                self.ratings[paper_id] = pd.Series(dtype=int)
                self.decisions[paper_id] = 'Unknown'

worker_list = []
start = 0
end = segment
link_list = list(df.link.items())
for i in range(num_of_workers):
    worker_list.append(Worker(link_list, start, min(end, total_len)))
    start += segment
    end += segment

for i in range(num_of_workers):
    worker_list[i].start()

ratings = dict()
decisions = dict()  # 2022.11.12 has no decisions
for i in range(num_of_workers):
    worker_list[i].join()
    ratings.update(worker_list[i].ratings)


df = pd.DataFrame(ratings).T
# df['decision'] = pd.Series(decisions)
df.index.name = 'paper_id'
df.to_csv('ratings.tsv', sep='\t')
