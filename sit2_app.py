import requests
import xml.etree.ElementTree as ET
# import pandas as pd
import os
import random
import re
from flask import Flask, request, send_file, jsonify
from fuzzywuzzy import process, fuzz
from pytrends.request import TrendReq
from urllib.parse import urljoin
# from urllib.parse import urlparse

app = Flask(__name__)

project_dir = os.path.abspath(os.path.dirname(__file__))

def fetch_sitemap(url, auth=None):
    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()
        # print(response.text, "jddvdnvsdvnsdd")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching sitemap: {e}")
        return None


def parse_sitemap(xml_data, folder_filters):

    root = ET.fromstring(xml_data)
    namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    folder_filters=""
    # Construct the list of URLs using list comprehension
    if not folder_filters:
        urls = [url.text for url in root.findall('ns:url/ns:loc', namespace)]
    else:
        # Construct the list of URLs using list comprehension
        urls = [url.text for url in root.findall('ns:url/ns:loc', namespace) 
                if any(filter in url.text for filter in folder_filters)]
    return urls
    
    # except Exception as e:
    #     return f"Error parsing sitemap: {e}"


# def read_urls_from_csv(csv_file):
#     try:
#         df = pd.read_csv(csv_file)
#         urls = df['Competitor URLs'].tolist()
#         print(urls, "urlskcc")
#         return urls
#     except Exception as e:
#         print(f"Error reading CSV file: {e}")
#         return []

def clean_url(url, irrelevant_keywords=None):
    irrelevant_keywords = ['investing', 'best', 'review', 'cryptocurrency', 'financial advisor', 'robots', 'advisor']
    url_parts = url.rstrip('/').split("/")
    # print(url_parts, "url pratshas")
    # Extract the path component from the parsed URL
    last_part = url_parts[-1]
    # Remove irrelevant keywords
    for keyword in irrelevant_keywords:
        keyword_pattern = r'\b' + re.escape(keyword) + r'\b'
        last_part = re.sub(keyword_pattern, '', last_part)
    
    # Replace hyphens with spaces
    cleaned_url = last_part.replace('-', ' ')
    # Remove digits and non-alphabetic characters
    cleaned_url = re.sub(r'[^a-zA-Z0-9\s]', '', cleaned_url)
    # Remove extra spaces
    cleaned_url = re.sub(r'\s+', ' ', cleaned_url).strip()
    # print(cleaned_url, "clsaskcsjkcs")
    return cleaned_url

def find_closest_match(keyword, candidates):
    closest_match, score = process.extractOne(keyword, candidates, scorer=fuzz.token_sort_ratio)
    return closest_match if score else None

def determine_content_opportunity(score):
    if score == 100:
        return "Existing page"
    elif 85 <= score < 100:
        return "Potentially existing"
    else:
        return "Content opportunity"


def get_google_trends_score(keyword):
    print(f"Fetching Google Trends data for keyword: {keyword}")
    pytrends = TrendReq(hl='en-US', tz=360)
    try:
        pytrends.build_payload([keyword], cat=0, timeframe='today 12-m', geo='', gprop='')
        data = pytrends.interest_over_time()
        if not data.empty:
            return round(data[keyword].mean(), 2)
        return 0
    except Exception as e:
        print(f"Error fetching Google Trends data for {keyword}: {e}")
        return 0

# def get_http_auth():
#     username = 'abc'
#     password = 1234
#     return (username, password)

def parse_robots_txt(url):
    robots_url = urljoin(url, '/robots.txt')
    response = requests.get(robots_url)
    lines = response.text.split('\n')
    sitemap_urls = []
    for line in lines:
        if line.startswith('Sitemap:'):
            sitemap_urls.append(line.split(':', 1)[1].strip())
    return sitemap_urls

def create_comparison_csv(all_urls, regular_primary_keywords, techopedia_matches, similarity_scores, filename):
    techopedia_similar_urls = [match[0] for match in techopedia_matches]
    content_opportunities = [determine_content_opportunity(score) for score in similarity_scores]

    file_count = 0
    original_filename = filename
    while os.path.exists(filename):
        file_count += 1
        filename = f"{os.path.splitext(original_filename)[0]}_{file_count}.csv"

    # df = pd.DataFrame({
    #     'Competitor URLs': all_urls,
    #     'Primary Keyword': regular_primary_keywords,
    #     'Similarity': similarity_scores,
    #     'Content Opportunity': content_opportunities,
    #     # 'Google Trends': google_trends_scores,
    #     'Techopedia Similar URLs': techopedia_similar_urls,
    # })
    # df.to_csv(filename, index=False)
    
    output_list = []

    for url, opportunity, keyword, similarity, tech_url in zip(all_urls, content_opportunities, regular_primary_keywords, similarity_scores, techopedia_similar_urls):
        data_point = {
            'competitor_urls': url,
            'content_opportunity': opportunity,
            'primary_keyword': keyword,
            'similarity': similarity,
            'techopedia_similar_urls': tech_url,
        }
        output_list.append(data_point)

    return output_list
        

    # df2 = {
    #     'competitor_urls': all_urls,
    #     'primary_keyword': regular_primary_keywords,
    #     'similarity': similarity_scores,
    #     'content_opportunity': content_opportunities,
    #     # 'google_trends': google_trends_scores,
    #     'techopedia_similar_urls': techopedia_similar_urls,
    # }

    # return df2


@app.route('/scrap_data', methods=["POST", "GET"])
def scrap_func():
    if request.method == "POST":
        comp_sit = request.form["comp_sitemap_url"]
        comp_filt = request.form["comp_filters"]
        comp_key = request.form["comp_keywords"]
        tec_sit = request.form["technopedia_sitemap"]
        tec_fil = request.form["technopedia_filters"]
        tec_key = request.form["technopedia_keywords"]

        # data_source_option = '1'

        try:
            # if data_source_option == '1':
            sitemap_urls_input = comp_sit
            folder_filters = comp_filt
            folder_filters = [filter.strip() for filter in folder_filters.split(',')] if folder_filters else []
            keyword_input = comp_key

            # Prompt for HTTP authentication for competitor sitemap
            # use_auth_competitor = input("Do you want to use HTTP authentication for competitor sitemaps? (y/n): ")
            # use_auth_competitor = 'n'
            # auth_competitor = get_http_auth() if use_auth_competitor.lower() == 'y' else None
            # Generate combinations of filters with '/'
            combined_filters = []
            for i in range(len(folder_filters)):
                for j in range(i+1, len(folder_filters)):
                    combined_filters.append(folder_filters[i] + '/' + folder_filters[j])

        # Extend folder_filters with combined filters
            folder_filters.extend(combined_filters)
            auth = None  # No authentication for sitemap URLs

            all_urls = []
            for sitemap_url in sitemap_urls_input.split(','):
                xml_data = fetch_sitemap(sitemap_url.strip(), auth=auth)
                all_urls.extend(parse_sitemap(xml_data, folder_filters))
            # print("all_urls",all_urls)
            regular_primary_keywords = [clean_url(url, keyword_input.split(',')) for url in all_urls]
            # print(regular_primary_keywords, "shbsjksns")
            ####2   
            technopedia_urls_input = tec_sit
            technopedia_filters = tec_fil
            technopedia_filters = [filter.strip() for filter in technopedia_filters.split(',')] if technopedia_filters else []
            technopedia_input = tec_key

            # Prompt for HTTP authentication for competitor sitemap
            # use_auth_competitor = input("Do you want to use HTTP authentication for techopedia sitemaps? (y/n): ")
            # use_auth_competitor = 'n'
            # auth_competitor = get_http_auth() if use_auth_competitor.lower() == 'y' else None
            # Generate combinations of filters with '/'
            combined_filters = []
            for i in range(len(technopedia_filters)):
                for j in range(i+1, len(technopedia_filters)):
                    combined_filters.append(technopedia_filters[i] + '/' + technopedia_filters[j])

        # Extend folder_filters with combined filters
            technopedia_filters.extend(combined_filters)
            auth = None  # No authentication for sitemap URLs

            technopedia_urls = []
            for technopedia_url in technopedia_urls_input.split(','):
                xml_data = fetch_sitemap(technopedia_url.strip(), auth=auth)
                technopedia_urls.extend(parse_sitemap(xml_data, technopedia_filters))

            
            # technopedia_robots_urls_input = input("Enter website URLs to fetch sitemaps from robots.txt separated by commas (leave blank to skip): ")
            # if technopedia_robots_urls_input.strip():
            #     for robots_url in robots_urls_input.split(','):
            #         technopedia_urls.extend(parse_robots_txt(robots_url.strip()))

            techopedia_primary_keywords = [clean_url(url, technopedia_input.split(',')) for url in technopedia_urls]

        # elif data_source_option == '2':
        #     csv_file = input("Enter the path to the CSV file: ")
        #     all_urls = read_urls_from_csv(csv_file)

        # else:
        #     print("Invalid choice.")
        #     exit()


        # print("Analysis completed.")

        # unique_primary_keywords = set(regular_primary_keywords)

        # google_trends_scores_unique = {}
        # for keyword in unique_primary_keywords:
        #     if keyword:  
        #         score = get_google_trends_score(keyword)
        #         google_trends_scores_unique[keyword] = score
        #         time.sleep(2)

        # mapped_google_trends_scores = [google_trends_scores_unique.get(keyword, 0) for keyword in regular_primary_keywords]

            techopedia_matches = []
            similarity_scores = []
            for primary_keyword in regular_primary_keywords:
                match_result = process.extractOne(primary_keyword, techopedia_primary_keywords, scorer=fuzz.token_sort_ratio)
                if match_result is not None:
                    match_keyword, score = match_result
                    match_index = techopedia_primary_keywords.index(match_keyword)
                    techopedia_match_url = technopedia_urls[match_index]
                else:
                    match_keyword, score = None, 0
                    techopedia_match_url = ''
                
                techopedia_matches.append((techopedia_match_url, match_keyword))
                similarity_scores.append(score)

            numn = random.randint(1, 9999)
            out_file = f"{project_dir}/output/output_comparison{numn}.csv"

            a = create_comparison_csv(all_urls, regular_primary_keywords, techopedia_matches, similarity_scores, out_file)
            print("Analysis completed.")

            dic = {
                    "success": True,
                    "message": "successful response!",
                    "data": {
                        "result": a
                        # "file_path": f'download/output_comparison{numn}.csv'
                    }
                }

            return dic
        
        except:
            dic = {
                "success": False,
                "message": "XML parse error",
                "data": {}
            }

            return dic
        
    

@app.route('/download/<file>',methods=["POST","GET"])
def download(file):
    return send_file(f"{project_dir}/output/{file}", as_attachment=True)
    

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8086, debug=False, threaded=True)

