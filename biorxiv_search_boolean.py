# Source code: https://github.com/blairbilodeau/arxiv-biorxiv-search/blob/master/biomedrxiv_search_function.py

#####
# Created by Blair Bilodeau
# Last modified May 22, 2020

#####
# Inspired by:
# https://pypi.org/project/arxiv-checker/
# https://github.com/mahdisadjadi/arxivscraper (more relevant)

#####
# Resources:
# https://www.biorxiv.org/search
# https://www.medrxiv.org/search

######################################################################

import math
import os
import pandas as pd
import datetime
import time
import sys
import string
import gc
import requests
import itertools
from bs4 import BeautifulSoup as bs

#######
## Main function
## Parameters:
# sdate        - datetime object        - starting date of search period 
# fdate        - datetime object        - end date of search period
# journal      - str                    - biorxiv or medrxiv
# kwd          - list of str            - keywords to search for in title and abstract
# kwd_type     - 'all' or 'any'         - whether all keywords are required or just one of them
# athr         - list of max 2 str      - authors which are required
# subjects     - list of str            - subject options are:
#                                         (Note capitalization and spacing are important for subject)
#                                               BIORXIV
#                                           Animal Behaviour and Cognition, Biochemistry, Bioengineering, Bioinformatics,
#                                           Biophysics, Cancer Biology, Cell Biology, Clinical Trials, Developmental Biology,
#                                           Ecology, Epidemiology, Evolutionary Biology, Genetics, Genomics, Immunology,
#                                           Microbiology, Molecular Biology, Neuroscience, Paleontology, Pathology, 
#                                           Pharmacology and Toxicology, Physiology, Plant Biology, Scientific Communication and Education,
#                                           Synthetic Biology, Systems Biology, Zoology
#                                               MEDRXIV
#                                           Addiction Medicine, Allergy and Immunology, Anesthesia, Cardiovascular Medicine, 
#                                           Dentistry and Oral Medicine, Dermatology, Emergency Medicine, Endocrinology,
#                                           Epidemiology, Forensic Medicine, Gastroenterology, Genetic and Genomic Medicine, Geriatric Medicine, 
#                                           Health Economics, Health Informatics, Health Policy, Health Systems and Quality Improvement, 
#                                           Hematology, HIV/AIDS, Infectious Diseases (except HIV/AIDS), Intensive Care and Critical Care Medicine, 
#                                           Medical Education, Medical Ethics, Nephrology, Neurology, Nursing, Nutrition, Obstetrics and Gynecology, 
#                                           Occupational and Environmental Health, Oncology, Ophthalmology, Orthopedics, Otolaryngology, Pain Medicine, 
#                                           Palliative Medicine, Pathology, Pediatrics, Pharmacology and Therapeutics, Primary Care Research, 
#                                           Psychiatry and Clinical Psychology, Public and Global Health, Radiology and Imaging, Rehabilitation Medicine and Physical Therapy, 
#                                           Respiratory Medicine, Rheumatology, Sexual and Reproductive Health, Sports Medicine, Surgery, Toxicology, 
#                                           Transplantation, Urology
# max_records  - int                    - maximum number of results to return
# max_time     - float                  - maximum amount of seconds to be spent searching 
# cols         - list                   - biorxiv fields to extract
#                                           column options are:
#                                           title, authors, date, url
# abstract     - bool                   - whether to extract the abstract of every paper returned by search 
#                                           (potentially very time consuming)

def biomedrxivsearch(start_date = datetime.date.today().replace(day=1), 
    end_date = datetime.date.today(), 
    subjects = [], 
    journal = 'biorxiv',
    kwd = [], 
    kwd_type = 'all', 
    athr = [], 
    max_records = 75, 
    max_time = 300,
    cols = ['title', 'authors', 'date', 'url'],
    abstracts = False,
    print_url = False):

    ## keep track of timing
    overall_time = time.time()

    ## url

    BASE = 'http://{:s}.org/search/'.format(journal)
    url = BASE

    ## format dates
    start_date = str(start_date)
    end_date = str(end_date)

    ## format inputs
    journal = journal.lower()
    kwd_type = kwd_type.lower()

    ### build the url string

    ## journal selection
    journal_str = 'jcode%3A' + journal
    url += journal_str

    ## subject selection
    if len(subjects)>0:
        first_subject = ('%20').join(subjects[0].split())
        subject_str = 'subject_collection_code%3A' + first_subject
        for subject in subjects[1:]:
            subject_str = subject_str + '%2C' + ('%20').join(subject.split())
        url += '%20' + subject_str

    ## keyword selection
    if len(kwd) > 0:
        kwd_str = 'abstract_title%3A' + ('%252C%2B').join([kwd[0]] + [('%2B').join(keyword.split()) for keyword in kwd[1:]])
        kwd_str = kwd_str + '%20abstract_title_flags%3Amatch-' + kwd_type
        url += '%20' + kwd_str

    ## author selection
    if len(athr) == 1:
        athr_str = 'author1%3A' + ('%2B').join(athr[0].split())
        url += '%20' + athr_str
    if len(athr) == 2:
        athr_str = 'author1%3A' + ('%2B').join(athr[0].split()) + '%20author2%3A' + ('%2B').join(athr[1].split())
        url += '%20' + athr_str

    ## date range string
    date_str = 'limit_from%3A' + start_date + '%20limit_to%3A' + end_date
    url += '%20' + date_str

    ## fixed formatting
    num_page_results = 75
    url += '%20numresults%3A' + str(num_page_results) + '%20format_result%3Acondensed' + '%20sort%3Arelevance-rank'

    ## lists to store date
    titles = []
    author_lists = []
    urls = []
    dates = []

    if print_url:
        print ("URL for search:", url)
    ### once the string has been built, access site

    # initialize number of pages to loop through
    page = 0

    ## loop through other pages of search if they exist
    while True:

        # access url and pull html data
        if page == 0:
            url_response = requests.post(url)
            html = bs(url_response.text, features='html.parser')

            # find out how many results there are, and make sure don't pull more than user wants
            num_results_text = html.find('div', attrs={'class': 'highwire-search-summary'}).text.strip().split()[0]
            if num_results_text == 'No':
                print('No results found matching search criteria.', kwd)
                return None

            num_results = int(num_results_text)
            num_fetch_results = min(max_records, num_results)
        
        else:
            page_url = url + '?page=' + str(page)
            url_response = requests.post(page_url)
            html = bs(url_response.text, features='html.parser')

        # list of articles on page
        articles = html.find_all(attrs={'class': 'search-result'})
    
        ## pull details from each article on page
        titles += [article.find('span', attrs={'class': 'highwire-cite-title'}).text.strip() if article.find('span', attrs={'class': 'highwire-cite-title'}) is not None else None for article in articles]
        author_lists += [[author.text for author in article.find_all('span', attrs={'class': 'highwire-citation-author'})] for article in articles]
        
        urls += ['http://www.{:s}.org'.format(journal) + article.find('a', href=True)['href'] for article in articles]

        dates += [('-').join(article.find('div', attrs={'class': 'highwire-article-citation highwire-citation-type-highwire-article'}).get('data-pisa').strip().split(';')[1].split('.')[0:3]) for article in articles]

        ## see if too much time has passed or max number of records reached or no more pages
        if time.time() - overall_time > max_time or (page+1)*num_page_results >= num_fetch_results:
            break

        page += 1

    records_data = list(zip(*list(map(lambda dummy_list: dummy_list[0:num_fetch_results], [titles, author_lists, urls, dates]))))
    
    full_records_df = pd.DataFrame(records_data, columns=['title', 'authors', 'url', 'date'])

    if num_results > max_records:
        print('Max number of records ({:d}) reached. Fetched in {:.1f} seconds.'.format(max_records, time.time() - overall_time))
    elif time.time() - overall_time > max_time:
        print('Max time ({:.0f} seconds) reached. Fetched {:d} records in {:.1f} seconds.'.format(max_time, num_fetch_results, time.time() - overall_time))
    else:
        print('Fetched {:d} records in {:.1f} seconds.'.format(num_fetch_results, time.time() - overall_time))
    
    ## check if abstracts are to be pulled
    if abstracts:
        print('Fetching abstracts for {:d} papers...'.format(len(full_records_df)))
        full_records_df['abstract'] = [bs(requests.post(paper_url).text, features='html.parser').find('div', attrs={'class': 'section abstract'}).text.replace('Abstract','').replace('\n','') for paper_url in full_records_df.url]
        print('Abstracts fetched.')

    return(full_records_df)

def save_csv(records_df, journal = 'biorxiv', export = './', exportfile = ''):
    if export != '':
        if exportfile == '':
            exportfile = datetime.date.today().strftime('%Y-%m-%d') + '-{:s}-metadata.csv'.format(journal)
        exportpath = export + exportfile
        print('Exporting records as csv to {:s}...'.format(exportpath))
        records_df.to_csv(exportpath, index=False)
        print('Export complete.')
    else:
        print ('Define the folder path to save csv!')

def download_pdf(records_df, download='pdfs/'):
    
    print('Downloading {:d} PDFs to {:s}...'.format(len(records_df['title']), download))
    pdf_urls = [url + '.full.pdf' for url in records_df.url] # list of urls to pull pdfs from

    # create filenames to export pdfs to
    # currently setup in year_lastname format
    pdf_lastnames_full = ['_'.join([name.split()[-1] for name in namelist]) for namelist in records_df.authors] # pull out lastnames only
    pdf_lastnames = [name if len(name) < 200 else name.split('_')[0] + '_et_al' for name in pdf_lastnames_full] # make sure file names don't get longer than ~200 chars
    pdf_paths = [download + date + '_' + lastname + '.pdf' for date,lastname in zip(records_df.date, pdf_lastnames)] # full path for each file
    # export pdfs
    for paper_idx in range(len(pdf_urls)):
        response = requests.get(pdf_urls[paper_idx])
        file = open(pdf_paths[paper_idx], 'wb')
        file.write(response.content)
        file.close()
        gc.collect()
    print('Download complete.')

def search_several_topics_AND_OR(topics, 
                                 start_date = datetime.date.today().replace(day=1), 
                                 end_date = datetime.date.today(), 
                                 subjects = ['Clinical Trials', 'Bioengineering'], 
                                 journal = 'biorxiv',
                                 max_records = 75, 
                                 max_time = 300,
                                 cols = ['title', 'authors', 'date', 'url'],
                                 abstracts = False):

    record_dfs = []
    for topic in topics:
        df = biomedrxivsearch(start_date = start_date, 
                             end_date = datetime.date.today(), 
                             journal = 'biorxiv',
                             subjects = subjects, 
                             kwd = topic, 
                             kwd_type = 'all',
                             abstracts = abstracts,
                             max_records = max_records,
                             max_time = max_time)
        record_dfs.append(df)
    
    full_df = pd.concat(record_dfs, sort=True)
    print ('Before drop duplicates:', len(full_df))
    full_df.drop_duplicates('title', inplace=True)
    print ('After drop duplicates:', len(full_df))
    full_df.reset_index(drop=True, inplace=True)
    return full_df

def search_several_topics_OR_AND(topics, 
                                 start_date = datetime.date.today().replace(day=1), 
                                 end_date = datetime.date.today(), 
                                 subjects = ['Clinical Trials', 'Bioengineering'], 
                                 journal = 'biorxiv',
                                 max_records = 75, 
                                 max_time = 300,
                                 cols = ['title', 'authors', 'date', 'url'],
                                 abstracts = False,
                                 delay = 0.5):

    """ Search for keyword options from topics: one kw from each topic

        Parameters:
            delay - s (delay if you are being rate limited)
    """

    record_dfs = []
    for kwd in list(itertools.product(*topics)):
        time.sleep(delay)
        kwd_list = list(kwd)
        df = None
        df = biomedrxivsearch(start_date = start_date, 
                             end_date = datetime.date.today(), 
                             journal = 'biorxiv',
                             subjects = subjects, 
                             kwd = kwd_list, 
                             kwd_type = 'all',
                             abstracts=abstracts,
                             max_records = max_records,
                             max_time = max_time)
        if df is not None:
            print ('Found smth for keywords:', kwd_list)
            df['kwd'] = [kwd for i in range(len(df))]
            record_dfs.append(df)
    full_df = pd.concat(record_dfs, ignore_index=True)
    print ('Before drop duplicates:', len(full_df))
    full_df.drop_duplicates('title', inplace=True)
    print ('After drop duplicates:', len(full_df))
    full_df.reset_index(drop=True, inplace=True)
    return full_df
        