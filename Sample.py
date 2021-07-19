import argparse
import base64
import json
import logging
import os
import shutil

import commonmark
import markdown
from bs4 import BeautifulSoup


def parse_reports(file_path, reports, outputpath, baseUrl, categories):
    """
    Parse reports to dictionary with necessary fields
    :param file_path: path to the reports to read from
    :param reports: list to store dictionary report
    :param outputpath: output dir path to store the parsed files
    :param baseUrl: server api url
    :param categories: distinct categories in all the reports
    :return:
    """
    report = {}
    try:
        with open(file_path, 'r') as file:
            file_content = file.read()
            file.close()
    except:
        logging.error("Failed to read from ", file_path)
    md = markdown.Markdown(extensions=['full_yaml_metadata'])
    md.convert(file_content)
    report.update(md.Meta)
    for x in report["report-categories"]:
        categories.add(x)
    parser = commonmark.Parser()
    ast = parser.parse(file_content)
    renderer = commonmark.HtmlRenderer()
    html = renderer.render(ast)
    soup = BeautifulSoup(html, "html.parser")
    if "title" not in report:
        fileName = os.path.basename(file_path)
        report["title"] = os.path.splitext(fileName)[0]
    report["title"] = report["title"].replace("/", " ")
    report["applications"] = report["applications"]
    logging.debug("Done parsing yaml content")
    parse_sections(soup, report, baseUrl)
    logging.debug("Done parsing sections")
    if 'image' in report:
        image_name = report["image"]
        image_url = baseUrl + "/reports/images/" + image_name
        report["image-url"] = image_url
        del report["image"]
    json_string = json.dumps(report)
    report_name = report["title"]
    report_name = report_name.replace(" ", "-") + ".json"
    with open(os.path.join(outputpath + "/reports/", report_name), "w") as file:
        file.write(json_string)
        file.close()
    logging.debug("report: ", report)
    reports.append(report)

def parse_sections(soup, report, baseUrl):
    """
    To parse overview,configuration and use cases sections and convert to base64 string
    :param soup: An instance of Beautiful Soup to navigate html content
    :param report: Dictionary to store the fields for json report
    :return:
    """
    parse_sections = False  # To parse section wise set it to True else full content is parsed
    overview = False
    config = False
    usecase = False
    overview_content = ""
    config_content = ""
    usecases_content = ""
    isFullContent = False
    full_content = ""
    updateImgUrl(baseUrl, soup)
    for e in soup.contents:
        if not parse_sections:
            if 'h1' == str(e.name).lower():
                isFullContent = True
            if isFullContent:
                full_content += "\n" + str(e)
        else:
            content_value = e.next
            if content_value == 'Overview':
                overview = True
            if content_value == 'Configuration':
                config = True
                overview = False
            if content_value == 'Use Cases':
                usecase = True
                config = False
            if overview == True and config == False and usecase == False:
                overview_content += "\n" + str(e)
            if overview == False and config == True and usecase == False:
                config_content += "\n" + str(e)
            if overview == False and config == False and usecase == True:
                usecases_content += "\n" + str(e)

    if not parse_sections:
        report["content"] = convert_to_base64(full_content)
    else:
        if overview_content:
            report["overview"] = convert_to_base64(overview_content)
        if config_content:
            report["configuration"] = convert_to_base64(config_content)
        if usecases_content:
            report["use_cases"] = convert_to_base64(usecases_content)

def updateImgUrl(baseUrl, soup):
    images = soup.findAll('img')
    for img in images:
        imageSrc = img.attrs.get("src")
        srcDict = {"src": baseUrl + "/reports/" + imageSrc}
        img.attrs.update(srcDict)

def convert_to_base64(str):
    """
    Convert plain string to base64 string
    :param str: content passed to convert it to base64 string
    :return: content converted to base64
    """
    str_bytes = str.encode("utf-8")
    str_bytes_base64 = base64.b64encode(str_bytes)
    str_base64 = str_bytes_base64.decode("utf-8")
    return str_base64

def main(args):
    baseUrl = args.base_url
    inputpath = args.root_dir
    outputdir = args.output_dir_name
    outputpath = os.path.join(inputpath, outputdir)
    if os.path.exists(outputpath):
        logging.error("Directory with name \"%s\" already exits! ", outputdir)
    else:
        logging.debug("base_url " + baseUrl + " root_dir " + inputpath + " output path " + outputpath)
        reports = []
        categories = set()
        categories_list = []
        logging.info("Started parsing files..")
        for dirpath, dirnames, filenames in os.walk(inputpath):
            structure = os.path.join(outputpath, dirpath[len(inputpath):])
            os.mkdir(structure)
            for name in filenames:
                old_file_path = os.path.join(dirpath, name)
                new_file_path = os.path.join(structure, name)
                if "/images" in old_file_path:
                    shutil.copyfile(old_file_path, new_file_path)
                if old_file_path.endswith(".md") and "/reports" in old_file_path:
                    parse_reports(old_file_path, reports, outputpath, baseUrl, categories)
        json_string = json.dumps(reports)
        with open(os.path.join(outputpath + "/reports", "reports.json"), "w") as file:
            file.write(json_string)
            file.close()
        logging.debug("generated reports.json")
        parse_categories(categories, categories_list, reports)
        json_string = json.dumps(categories_list)
        with open(os.path.join(outputpath + "/reports", "categories.json"), "w") as file:
            file.write(json_string)
            file.close()
        logging.debug("generated categories.json")
        logging.info("Done parsing files, json reports are stored at " + outputpath)

def parse_categories(categories, categories_list, reports):
    """
    Add all reports that belong to that each category
    :param categories: set of categories
    :param categories_list: final list of categories and its reports
    :param reports: list of parsed reports
    :return:
    """
    remove_list = ["overview", "configuration", "use_cases", "content"]
    for distinct_category in categories:
        report_categories = []
        category = {}
        for report_doc in reports:
            if distinct_category in report_doc["report-categories"]:
                category["category"] = distinct_category
                category["description"] = ""
                for x in remove_list:
                    if x in report_doc:
                        del report_doc[x]
                report_categories.append(report_doc)
        category["reports"] = report_categories
        categories_list.append(category)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser(description='Parsing markdown file')
    parser.add_argument('--base_url', type=str, help='Base url for the resource', required=True)
    parser.add_argument('--root_dir', type=str, help='Parent directory contents to parse',
                        required=True)
    parser.add_argument('--output_dir_name', type=str,
                        help='Name of the destination directory for the parsed files to store',
                        required=True)
    args = parser.parse_args()
    main(args)
