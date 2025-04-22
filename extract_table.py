import requests
from bs4 import BeautifulSoup

def extract_ipl_points_table(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}  # Adding User-Agent
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.content, "html.parser")

        # Find the table - you might need to adjust the selector
        table = soup.find("table")  #  or e.g., soup.find("table", class_="your-table-class")

        if not table:
            return {"error": "Could not find the table element on the page."}

        rows = table.find_all("tr")
        if not rows:
             return {"error": "Could not find table rows."}


        headers = [th.text.strip() for th in rows[0].find_all("th")]
        table_data = {}

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) == len(headers):
                team_name = cells[0].text.strip()
                table_data[team_name] = {}
                for i in range(1, len(headers)):
                    header = headers[i]
                    if header == "M":
                        header = "Matches"
                    elif header == "W":
                        header = "Wins"
                    elif header == "PT":
                        header = "Points"
                    table_data[team_name][header] = cells[i].text.strip()

        return {"tableData": table_data}

    except requests.exceptions.RequestException as e:
        return {"error": f"Error fetching URL: {e}"}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

url = "https://www.espncricinfo.com/series/ipl-2025-1449924/points-table-standings"  # Replace with the actual URL if different
result = extract_ipl_points_table(url)

if "error" in result:
    print(result["error"])
else:
    print(result["tableData"])  # Prints the extracted data in the desired format