import argparse
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import os
import builtwith
from concurrent.futures import ThreadPoolExecutor, as_completed

# Selenium driver configuration
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run the browser in headless mode (no GUI)
service = Service('/usr/local/bin/chromedriver')  # Change this path to your ChromeDriver path

def check_http_service(url):
    try:
        response = requests.get(url, timeout=3)  # Reduce the timeout if possible
        if response.status_code == 200:
            return True, response.url, response.headers
        else:
            return False, None, None
    except requests.RequestException:
        return False, None, None

def take_screenshot(url, output_path):
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_window_size(1920, 1080)  # Computer screen size
    driver.get(url)
    driver.save_screenshot(output_path)
    driver.quit()

def detect_technologies(url):
    try:
        technologies = builtwith.parse(url)
        tech_list = []
        for tech, items in technologies.items():
            tech_list.extend(items)
        return tech_list
    except Exception as e:
        print(f"Error detecting technologies for {url}: {e}")
        return []

def check_security_headers(headers):
    required_headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "default-src 'self'"
    }
    missing_headers = []
    for header, expected_value in required_headers.items():
        if header not in headers or headers[header] != expected_value:
            missing_headers.append(header)
    return missing_headers

def process_domain(domain, ports):
    results = []
    for port in ports:
        protocol = 'http' if port == 80 else 'https'
        url = f"{protocol}://{domain}:{port}"
        service_available, redirected_url, headers = check_http_service(url)

        if service_available:
            screenshot_path = f"screenshots/{domain}_{port}.png"
            take_screenshot(redirected_url, screenshot_path)
            technologies = detect_technologies(redirected_url)
            missing_headers = check_security_headers(headers)
            results.append({
                'domain': domain,
                'port': port,
                'status': 'Service available',
                'screenshot': screenshot_path,
                'redirected_url': redirected_url,
                'technologies': technologies,
                'missing_headers': missing_headers
            })
        else:
            results.append({
                'domain': domain,
                'port': port,
                'status': 'No HTTP service found on this port',
                'screenshot': None,
                'redirected_url': None,
                'technologies': None,
                'missing_headers': None
            })
    return results

def write_html(results, output_html):
    soup = BeautifulSoup("""
    <html>
    <head>
        <title>Screenshit - Results</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; color: #333; }
            h1 { color: #333; text-align: center; }
            h2 { color: #555; }
            .result { border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; background: #fff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .screenshot { width: 100%; max-width: 800px; border: 1px solid #ddd; margin-top: 10px; border-radius: 5px; }
            .technologies, .headers { font-style: italic; color: #666; }
            .headers { color: #f00; }
            .header { background-color: #4CAF50; color: white; text-align: center; padding: 10px 0; border-radius: 8px; }
            .content { max-width: 900px; margin: auto; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Screenshit - Results</h1>
        </div>
        <div class="content">
        </div>
    </body>
    </html>
    """, 'html.parser')

    body = soup.find('div', class_='content')

    for result in results:
        domain_info = soup.new_tag('div', **{'class': 'result'})

        domain_info.append(soup.new_tag('h2'))
        domain_info.h2.string = f"Domain/IP: {result['domain']} - Port: {result['port']}"

        status = soup.new_tag('p')
        status.string = f"Status: {result['status']}"
        domain_info.append(status)

        if result['redirected_url']:
            redirected = soup.new_tag('p')
            redirected.string = f"Redirected to: {result['redirected_url']}"
            domain_info.append(redirected)

        if result['screenshot']:
            img_tag = soup.new_tag('img', src=result['screenshot'], alt="Screenshot", **{'class': 'screenshot'})
            domain_info.append(img_tag)

        if result['technologies']:
            tech_list = ', '.join(result['technologies'])
            technologies = soup.new_tag('p', **{'class': 'technologies'})
            technologies.string = f"Detected Technologies: {tech_list}"
            domain_info.append(technologies)

        if result['missing_headers']:
            headers = ', '.join(result['missing_headers'])
            headers_info = soup.new_tag('p', **{'class': 'headers'})
            headers_info.string = f"Missing Security Headers: {headers}"
            domain_info.append(headers_info)

        body.append(domain_info)

    with open(output_html, 'w') as html_file:
        html_file.write(str(soup))

def main(input_file, output_html, additional_ports):
    with open(input_file, 'r') as file:
        lines = [line.strip() for line in file.readlines()]

    results = []
    default_ports = [80, 443]
    ports = default_ports + additional_ports

    if not os.path.exists('screenshots'):
        os.makedirs('screenshots')

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_domain = {executor.submit(process_domain, domain, ports): domain for domain in lines}
        for future in as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                result = future.result()
                results.extend(result)
                print(f"Processed: {domain}")
                write_html(results, output_html)
            except Exception as exc:
                print(f"{domain} generated an exception: {exc}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scan domains/IPs for HTTP and HTTPS services.')
    parser.add_argument('input_file', help='Input file with the list of domains/IPs')
    parser.add_argument('-o', '--output', default='results.html', help='Output HTML file')
    parser.add_argument('-p', '--ports', nargs='+', type=int, default=[], help='Additional ports to scan')

    args = parser.parse_args()

    main(args.input_file, args.output, args.ports)
