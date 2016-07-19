# -*- coding: utf-8 -*-
"""
Created on Sun Jul 10 10:03:32 2016

@author: steven
"""

#%% import block
from lxml import html
import urllib3 as ul
HTTP = ul.PoolManager()
ul.disable_warnings()
from io import BytesIO
import sqlite3
import datetime
#%% function definitions
def create_db(cursor):
    """
    Creates a lawsuits database named patent_lawsuits.db, already connected to
    via the sqlite3 cursor argument
    """
    cursor.execute(
        "CREATE TABLE lawsuits \
        (title TEXT, dateFiled TEXT, url TEXT)"
    )
    # add the first case in memory
    cursor.execute("INSERT INTO lawsuits VALUES (?,?,?)",
                   ('R. Jennings Manufacturing Company, Inc. v. Hammer et al',
                    '1984-05-08',
                    '/florida/flmdce/8:1984cv00636/179585'))

def check_db_status(cursor):
    """
    Returns either the most recent date of a lawsuit filed in the db or
    the date of the first lawsuit in the justia records if the db is empty.
    Args:
        CURSOR: a sqlite cursor connected to patent_lawsuits.db
    Returns:
        a string in the format "YYYY-MM-DD" indicating the most recent filing
    """
    cursor.execute("SELECT * FROM sqlite_master WHERE type='table'")
    if cursor.fetchall() == []:
        # the database is empty
        create_db(cursor)
        return check_db_status(cursor)
    else:
        query = "SELECT MAX(date(dateFiled)) FROM lawsuits"
        cursor.execute(query)
        date = cursor.fetchone()[0]
        query = "SELECT * FROM lawsuits WHERE dateFiled=?"
        cursor.execute(query, (date,))
        return cursor.fetchone()
#%%
def get_page(url):
    "Gets, parses a html page, returns an lxml etree object"
    page = HTTP.request('GET', url)
    tree = html.parse(BytesIO(page.data))
    return tree

def get_next_page(page_tree):
    """
    Taking a justia patent dockets page, this function gets, parses, returns
    the next dockets page.
    Args:
        page_tree: a lxml etree object representing the input page html.
    Returns:
        a lxml etree object representing the next page's html.
    """
    search = page_tree.xpath('//a[text()="Next"]')
    # a list
    if len(search) == 1:
        new_url = "https://dockets.justia.com/" + search[0].attrib["href"]
        return get_page(new_url)
    elif len(search) > 1:
        for i in search:
            print(i.attrib)
        return None
    else:
        print("no new pages")
        return None

class Case(object):
    """
    A class representing a patent lawsuit from a dockets.justia search page
    Attributes:
        works: a boolean value indicating whether all other attributes were
                fetched
        date: the date the case was filed in a YYYY-MM-DD formatted string
        name: the title of the case
        url: a string containing the url of the case in dockets.justia.com
    """
    def __init__(self, case_div_etree):
        """
        Creates itself based on a lxml.etree_ElementTree object representing a
        div containing case details from a justia page
        """
        self.div = case_div_etree
        self.works = True
        self.date = self.get_date()
        self.url = self.get_url()
        self.name = self.get_name()

    def get_name(self):
        """
        Returns the title / case name of a case contained in a
        lxml.etree_ElementTree div object
        """
        if self.works == True:
            name_xpath = './a[@class="case-name"]/strong/text()'
            try:
                return self.div.xpath(name_xpath)[0]
            except IndexError:
                print("Missing case name / invalid xpath")
                self.works = False
                return None

    def get_url(self):
        """
        Returns the url referring within Justia to the case.
        """
        if self.works == True:
            url_xpath = './a[@class="case-name"]/@href'
            try:
                url = self.div.xpath(url_xpath)[0]
                url = url.replace('https://dockets.justia.com/docket', '')
                return url
            except IndexError:
                print("Invalid Xpath; no url returned")
                self.works = False
                return None

    def get_date(self):
        """
        Returns the filing date of the case
        """
        if self.works == True:
            date_xpath = './div/time/@datetime'
            try:
                date_str = self.div.xpath(date_xpath)[0]
                datetime_obj = datetime.datetime.strptime(date_str, '%b-%d-%y')
                return str(datetime_obj.date())
            except (ValueError, IndexError):
                print("Missing case date / invalid xpath")
                self.works = False
                return None

def get_case_details(page_tree, cutoff_date, cutoff_title):
    """
    Gets, inserts the details of all cases after the last entry in the db into
    the db
    Args:
        page_tree: a lxml.etree._ElementTree representing the html of
        a patent lawsuits page of dockets.justia.com
        cutoff_date: the date of the most recently lawsuit in the db
        cutoff_title: the title of the most recent lawsuit in the db
        cursor: the cursor to the sqlite patent_lawsuits db connection
    Returns:
        A list of tuples of case details:
            (dateFiled, # in YYYY-MM-DD format
            title,      # a string
            url       # a string)
    """
    output = []
    cases_remaining()
    try:
        gen = (i for i in page_tree.xpath('//div[@id="search-results"]/div'))
    except AttributeError:
        return (output, True)
        # no more pages
    for div in gen:
        case = Case(div)
        if case.date == cutoff_date:
            if case.name == cutoff_title:
                print("done")
                return (output, True)
            else:
                pass
        if case.works:
            output.append((case.name, case.date, case.url))
        else:
            raise ValueError("Case missing one or more properties")
    return (output, False)

def update_db(cutoff_date, cutoff_title):
    """
    Gets, inserts the details of all cases after the last entry in the db into
    the db
    Args:
        page_tree: a lxml.etree._ElementTree representing the html of
        a patent lawsuits page of dockets.justia.com
        cutoff_date: the date of the most recently lawsuit in the db
        cutoff_title: the title of the most recent lawsuit in the db
        cursor: the cursor to the sqlite patent_lawsuits db connection
    Returns:
        A list of tuples of case details:
            (dateFiled, # in YYYY-MM-DD format
            title,      # a string
            url         # a string)
    """
    page = get_page("https://dockets.justia.com/browse/noscat-10/nos-830?page=4830")
    more_left = True
    output = []
    while more_left:
        (output_tmp, more_left) = get_case_details(page, cutoff_date, cutoff_title)
        output += output_tmp
    return output

def get_justia_total():
    """
    Gets the total number of patent lawsuits in Justia
    Returns:
        the integer total of patent lawsuit dockets in the justia database
    """
    page = get_page("https://dockets.justia.com/browse/noscat-10/nos-830")
    texts = page.xpath("//div[@class='row-label extra']/text()")
    for i in texts:
        if 'cases' in i.lower():
            number = int(i.strip().split('of')[1].replace(',', ''))
            return number
    if len(texts) < 1:
        print("Incorrect xpath? No text returned")

def get_db_total(cursor):
    """
    Returns the number of lawsuits in the database
    Args:
        cursor: a squlite3.Cursor object for the connection to patent_lawsuits
    Returns:
        the integer of lawsuits in the database.
    """
    cursor.execute("SELECT COUNT(*) FROM lawsuits")
    return cursor.fetchone()[0]

def cases_remaining():
    "maintains a count of cases remaining to parse"
    global TOTAL
    try:
        TOTAL -= 10
        print(TOTAL)
    except NameError:
        TOTAL = get_justia_total() - get_db_total(CURSOR)
        cases_remaining()
#%%
if __name__ == '__main__':
    CONN = sqlite3.connect("patent_lawsuits.db")
    CURSOR = CONN.cursor()
    (PREV_NAME, PREV_DATE, PREV_URL) = check_db_status(CURSOR)
    OUTPUT = update_db(PREV_DATE, PREV_NAME)
    CURSOR.executemany("INSERT INTO lawsuits VALUES (?,?,?)", OUTPUT)
    CONN.commit()
#%%
#def get_case_details(page_tree,
#                     cutoff_date,
#                     cutoff_title,
#                     cursor,
#                     current_date=datetime.date.today()):
#    """
#    Args:
#        page_tree: a lxml.etree._ElementTree representing the html of
#        a patent lawsuits page of dockets.justia.com
#    Returns:
#        A list of tuples of case details:
#            (dateFiled, # in YYYY-MM-DD format
#            title,      # a string
#            url       # a string)
#    """
#    case_divs_xpath = '//div[@id="search-results"]/div'
#    gen = (i for i in page_tree.xpath(case_divs_xpath))
#    while True:
#        try:
#            div = next(gen)
#        except StopIteration:
#            page_tree = get_next_page(page_tree)
#            gen = (i for i in page_tree.xpath(case_divs_xpath))
#            div = next(gen)
#        case = Case(div)
#        current_date = case.date
#        if current_date == cutoff_date:
#            if case.name == cutoff_title:
#                break
#            else:
#                pass
#        if case.works:
#            cursor.execute("INSERT INTO lawsuits VALUES (?,?,?)",
#                           (case.name, case.date, case.url))
#%%

#%% Testing, to become final execution
CONN = sqlite3.connect("patent_lawsuits.db")
CURSOR = CONN.cursor()
#%%
#t = get_page("https://dockets.justia.com/browse/noscat-10/nos-830?page={}")
#%%
#%%
CURSOR.execute("DROP TABLE lawsuits")
#%%
CURSOR.execute("SELECT * FROM sqlite_master WHERE type='table'")
CURSOR.fetchall()
#%%
create_db(CURSOR)
#%%
CURSOR.execute("SELECT * FROM lawsuits")
CURSOR.fetchone()
#%%
#%%
#def get_name(div):
#    """
#    Returns the title / case name of a case contained in a
#    lxml.etree_ElementTree div object
#    """
#    name_xpath = './a[@class="case-name"]/strong/text()'
#    try:
#        return(div.xpath(name_xpath)[0])
#    except:
#        print("Missing case name / invalid xpath")
#        return(None)

#def get_url(div):
#    """
#    Returns the url referring within Justia to the case.
#    """
#    url_xpath = './a[@class="case-name"]/@href'
#    try:
#        return(div.xpath(url_xpath)[0])
#    except:
#        print("Invalid Xpath; no url returned")
#        return(None)

#def get_date(div):
#    """
#    Returns the filing date of the case
#    """
#    date_xpath = './div/time/@datetime'
#    # In the event of justia reformatting, this is likely to break.
#    # current format: [@class="color-boulder small-font"]
#    try:
#        return(div.xpath(date_xpath)[0])
#    except:
#        print("Missing case date / invalid xpath")
#        return(None)
#%%
