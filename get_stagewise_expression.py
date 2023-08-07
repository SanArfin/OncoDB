import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import pandas as pd

# Set user agent headers for requests
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
)


def get_clinical_profile_urls_from_oncodb(url, headers, data):
    # Calling oncodb server to get HTML page consisting information of gene and clinical profile url
    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        # Read the html body and extract profile url in the html table
        return read_html_page_and_get_profile_urls(response)
    else:
        print("Failed to retrieve the web page:", response.status_code)


def read_html_page_and_get_profile_urls(response):
    profiles_url = []
    soup = BeautifulSoup(response.text, "html.parser")
    # Get <table> dom element in the table
    html_tables = soup.find_all("table")
    for html_table in html_tables:
        rows = get_table_rows(html_table)
        for row in rows:
            # Got all cell in the  row
            cells = get_first_seven_cells_of_row(row)
            for cell in cells:
                # Check if the cell contains a link "<a> - represent links
                if is_cell_have_anchor(cell):
                    # find the link in the cell
                    link = get_link_from_anchor(cell)
                    # if contains below filter add it to the profile url
                    if is_profile_url_link(link):
                        profiles_url.append(link)
    return profiles_url


def get_table_rows(html_table):
    return html_table.find_all("tr")


def get_first_seven_cells_of_row(row):
    return row.find_all("td")[:6]


def is_cell_have_anchor(cell):
    return cell.find("a") > 0


def get_link_from_anchor(cell):
    return cell.find("a")["href"]


def is_profile_url_link(link):
    return "&stageSelect=cstage&dataOption_clinical=expression" in link


def parse_url_query_params(url):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    return query_params


def find_html_tables(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.find_all("table")


def process_html_tables(tables, params):
    for table in tables:
        rows = table.find_all("tr")
        if rows:
            headers = [cell.get_text(strip=True) for cell in rows[0].find_all("td")]
            if all(header in headers for header in ["Stage", "Samples", "Average", "Median", "Std", "ANOVA-pvalue"]):
                data = extract_table_data(rows[1:], params['customSub'])
                return data
            else:
                print("The table does not contain all the specified headers.")
        else:
            print("No rows found in the table.")
    return []


def extract_table_data(rows, custom_sub):
    data = []
    for row in rows:
        row_data = [cell.get_text(strip=True) for cell in row.find_all("td")]
        data.append(row_data + [custom_sub])
    return data


def get_stage_wise_gene_expression(url, headers):
    endpoint = "https://oncodb.org" + url
    query_params = parse_url_query_params(endpoint)
    params = {
        'geneChoice': query_params.get('geneChoice', [''])[0],
        'customSub': query_params.get('customSub', [''])[0],
        'cancerSelect': query_params.get('cancerSelect', [''])[0],
        'stageSelect': query_params.get('stageSelect', [''])[0],
        'dataOption_clinical': query_params.get('dataOption_clinical', [''])[0]
    }

    response = requests.get(endpoint, headers=headers, params=params)
    if response.status_code == 200:
        html_content = response.text
        tables = find_html_tables(html_content)

        if tables:
            data = process_html_tables(tables, params)
            return data
        else:
            print("No tables found on the page.")
    else:
        print("Failed to retrieve the web page:", response.status_code)
    return []


def write_excel_file(data, output_filename):
    df = pd.DataFrame(data, columns=["Stage", "Samples", "Average", "Median", "Std", "ANOVA-pvalue", "CustomSub"])
    df.to_excel(output_filename, index=False)


def main():
    # oncodb_url -> Address of oncodb server
    oncodb_url = 'https://oncodb.org/cgi-bin/clinical_nonvirus_search.cgi'
    headers = {'User-Agent': USER_AGENT}
    # OncoDb have data for many cancers e.g. stomach cancer, brain cancer etc. The below data
    # field filter out other cancer and only get data for HNSC from oncodb server
    data = {
        'dataOption_clinical': 'expression',
        'cancerSelect': 'HNSC',
        'stageSelect': 'cstage',
        'sigFilter': '0.5',
        'by_option': 'Anova'
    }
    # First we get the all the clinical profile urls which contains stagewise Median of gene expression
    profile_urls = get_clinical_profile_urls_from_oncodb(oncodb_url, headers, data)[:10]

    stage_wise_gene_expression_median_values = []

    # Once we have clinical profile urls we call these urls and read the html body to get the median
    # of gene expression value
    for profile_url in profile_urls:
        data = get_stage_wise_gene_expression(profile_url, headers)
        stage_wise_gene_expression_median_values.extend(data)

    # Once we get median of all gene expression we dump it into an excel
    write_excel_file(stage_wise_gene_expression_median_values, "output.xlsx")


if __name__ == "__main__":
    main()
