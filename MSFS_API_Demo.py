
# ©JL Simulation

import requests
import json
import customtkinter
from collections import defaultdict
from PIL import Image
import threading
import time
import re
import os

# Reading current token
def read_token():
    try:
        with open("token.json", "r") as file:
            data = json.load(file)
            return data.get("ApiToken", "")
    except FileNotFoundError:
        print("token.json Not found. Creating new file.")
        with open("token.json", "w") as file:
            json.dump({"ApiToken": ""}, file)
        return ""

# Writing new token in token.json
def write_token(new_token):
    with open("token.json", "w") as file:
        json.dump({"ApiToken": new_token}, file)

# Update token every 50 minutes
def update_token():
    while True:
        print("Renewing token...")
        response = requests.get(Token, cookies=cookies)
        if response.status_code == 200:
            new_cookies = response.cookies
            new_token = new_cookies.get("ApiToken")
            if new_token:
                print(f"Recieved new token : {new_token}")
                write_token(new_token)
                cookies["ApiToken"] = new_token
            else:
                print("token not found in cookies.")
        else:
            print(f"Error while renewing token : {response.status_code}")
        time.sleep(50 * 60)  # 50 minutes

# Initial token load
Vtoken = read_token()
cookies = {
    "ApiToken": Vtoken
}

# URLs
Token = "https://planner.flightsimulator.com/api/v1/token"
Chart_List_Template = "https://planner.flightsimulator.com/api/v1/charts/index/A%20%20%20%20%20%20{airport}%20?provider=LIDO"
Metar_URL_Template = "https://planner.flightsimulator.com/api/v1/weather/metar/{airport}"

# API Requests
def Request_to_api(url):
    response = requests.get(url, cookies=cookies)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Erreur {response.status_code} : {response.text}")
        return None

# Parse METAR Data
def parse_metar(metar_text):
    pattern = (
        r"(?P<icao>[A-Z]{4}) "  # ICAO
        r"(?P<time>\d{6}Z) "  # Time
        r"(?P<wind>\d{3}\d{2}KT) "  # Wind
        r"(?P<visibility>\d{4}) "  # Visibility
        r"(R[0-9]{2}[LR]?\d{4}[A-Z] )?"  # Runway visual range
        r"(?P<weather>[A-Z]{2,4}) "  # Weather phenomena
        r"(?P<clouds>OVC\d{3}|CLR|FEW|SCT|BKN) "  # Clouds
        r"(?P<temp_dewpoint>M?\d{2}/M?\d{2}) "  # Temperature / Dewpoint
        r"Q(?P<pressure>\d{4})"  # Barometric Pressure (QNH)
    )
    match = re.match(pattern, metar_text)
    if match:
        return match.groupdict()
    else:
        return {"raw": metar_text}

# Display METARs
def update_metar():
    airport = search_entry.get().strip().upper()
    if not airport:
        print("Airport not specified.")
        return

    metar_url = Metar_URL_Template.format(airport=airport)
    metar_data = Request_to_api(metar_url)

    for widget in main_content.winfo_children():
        widget.destroy()

    if metar_data:
        metar_text = metar_data.get("data", "METAR not available.")
        parsed_metar = parse_metar(metar_text)

        if "raw" in parsed_metar:
            label = customtkinter.CTkLabel(main_content, text=f"METAR for {airport} :\n{parsed_metar['raw']}", font=("Arial", 14), justify="left")
            label.pack(pady=20)
        else:
            label_text = f"""METAR for {airport} :
Time : {parsed_metar.get('time', 'N/A')}
Wind : {parsed_metar.get('wind', 'N/A')}
Visibility : {parsed_metar.get('visibility', 'N/A')} mètres
Weather : {parsed_metar.get('weather', 'N/A')}
Clouds : {parsed_metar.get('clouds', 'N/A')}
Temperature/Dewpoint : {parsed_metar.get('temp_dewpoint', 'N/A')}
Pressure : {parsed_metar.get('pressure', 'N/A')} hPa"""
            label = customtkinter.CTkLabel(main_content, text=label_text, font=("Arial", 14), justify="left")
            label.pack(pady=20)
    else:
        label = customtkinter.CTkLabel(main_content, text=f"Not possible to get METAR for {airport}.", font=("Arial", 14))
        label.pack(pady=20)

# Fetch and Display TAFs
def update_taf():
    airport = search_entry.get().strip().upper()
    if not airport:
        print("Airport not specified.")
        return

    # TAF URL
    taf_url = f"https://planner.flightsimulator.com/api/v1/weather/taf/{airport}"
    taf_data = Request_to_api(taf_url)

    for widget in main_content.winfo_children():
        widget.destroy()

    if taf_data:
        taf_text = taf_data.get("data", "TAF not available.")
        label = customtkinter.CTkLabel(
            main_content,
            text=f"TAF for {airport}:\n{taf_text}",
            font=("Arial", 14),
            justify="left"
        )
        label.pack(pady=20)
    else:
        label = customtkinter.CTkLabel(
            main_content,
            text=f"Unable to get TAF for {airport}.",
            font=("Arial", 14)
        )
        label.pack(pady=20)

def download_chart_pdf(guid):
    # Step 1 : Get PNG url via GUID
    pages_url = f"https://planner.flightsimulator.com/api/v1/charts/pages/{guid}"
    pages_response = Request_to_api(pages_url)

    if not pages_response or "pages" not in pages_response or not pages_response["pages"]:
        print("Impossible de récupérer l'URL du PNG.")
        return

    light_pdf_url = pages_response["pages"][0]["urls"]["light_png"]
    print(f"Charts URL : {light_pdf_url}")

    # Étape 2 : Get SAS Token
    sas_url = "https://planner.flightsimulator.com/api/v1/charts-sas"
    response = requests.get(sas_url, cookies=cookies)

    if response.status_code != 200 or not response.text.strip():
        print("Impossible to get SAS token. The response is nil or invalid.")
        return

    sas_response = response.text.strip()
    print(f"SAS Token : {sas_response}")

    # Adding SAS token to Chart URL
    pdf_url_with_sas = f"{light_pdf_url}?{sas_response}"
    print(f"Complete Chart URL : {pdf_url_with_sas}")

    # Étape 3 : Download The Chart (PNG)
    try:
        response = requests.get(pdf_url_with_sas, stream=True)
        response.raise_for_status()

        download_path = os.path.expanduser(f"~/Downloads/{guid}.png")
        with open(download_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        print(f"Chart Downloaded with succes in : {download_path}")
    except Exception as e:
        print(f"Error while downloading chart: {e}")


# Display Charts
def display_charts(chart_data, chart_type, container):
    for widget in container.winfo_children():
        widget.destroy()

    canvas = customtkinter.CTkCanvas(container, bg="#2C2F33", highlightthickness=0)
    canvas.pack(side="left", fill="both", expand=True)

    scrollbar = customtkinter.CTkScrollbar(container, command=canvas.yview)
    scrollbar.pack(side="right", fill="y")

    canvas.configure(yscrollcommand=scrollbar.set)

    scrollable_frame = customtkinter.CTkFrame(canvas, fg_color="transparent")
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    charts = chart_data.get(chart_type, [])
    for idx, chart in enumerate(charts):
        def on_click(chart=chart):
            print(f"Clicked on chart: {chart['Name']} - GUID: {chart['GUID']}")
            download_chart_pdf(chart['GUID'])

        button = customtkinter.CTkButton(
            scrollable_frame,
            width=250,
            height=150,
            corner_radius=10,
            fg_color="#2f323c",
            hover_color="#3c4048",
            text="",
            command=on_click,
        )
        button.grid(row=idx // 3, column=idx % 3, padx=10, pady=10)

        name_label = customtkinter.CTkLabel(button, text=f"Name: {chart['Name']}", font=("Arial", 12, "bold"),
                                            text_color="white")
        name_label.place(x=10, y=10)

        procedures_label = customtkinter.CTkLabel(button, text=f"Procedures: {', '.join(chart['Procedures'])}",
                                                  font=("Arial", 10), text_color="white")
        procedures_label.place(x=10, y=40)

        runways_label = customtkinter.CTkLabel(button, text=f"Runways: {', '.join(chart['Runways'])}",
                                               font=("Arial", 10), text_color="white")
        runways_label.place(x=10, y=70)

        guid_label = customtkinter.CTkLabel(button, text=f"GUID: {chart['GUID']}", font=("Arial", 10, "italic"),
                                            text_color="white")
        guid_label.place(x=10, y=100)

    scrollable_frame.update_idletasks()
    canvas.config(scrollregion=canvas.bbox("all"))


# Update Charts
def update_charts():
    global chart_data
    airport = search_entry.get().strip().upper()
    if not airport:
        print("Airport not specified.")
        return

    Chart_List = Chart_List_Template.format(airport=airport)
    chart_response = Request_to_api(Chart_List)

    # Cleans existings widgets
    for widget in main_content.winfo_children():
        widget.destroy()

    if chart_response and "charts" in chart_response:
        # Extract parsed data
        chart_data = extract_procedures(chart_response)
        if chart_data:
            display_charts(chart_data, "Departure", main_content)
        else:
            chart_data = {}
            label = customtkinter.CTkLabel(main_content, text="No valid data available.", font=("Arial", 14))
            label.pack(pady=20)
    else:
        # If no valid data is available Display Error message
        chart_data = {}
        label = customtkinter.CTkLabel(main_content, text=f"Impossible to get data for {airport}.", font=("Arial", 14))
        label.pack(pady=20)

# Extract Procedures
def extract_procedures(data):
    if not data or "charts" not in data:
        print("Invalid data or 'chart' key not available.")
        return None

    sorted_procedures = defaultdict(list)

    for chart_type, charts in data["charts"].items():
        for chart in charts:
            guid = chart.get("guid", "N/A")
            name = chart.get("name", "N/A")
            procedures = [proc.get("ident", "N/A") for proc in chart.get("procedures", [])]
            runways = [
                f"{runway.get('number', 'N/A')}{runway.get('designator', '')}"
                for runway in chart.get("runways", [])
            ]

            if chart_type in ["SID"]:
                tab = "Departure"
            elif chart_type in ["STAR"]:
                tab = "Arrival"
            elif chart_type in ["IAC"]:
                tab = "Approach"
            elif chart_type in ["APC", "AFC", "AGC", "AOI"]:
                tab = "Airport"
            else:
                tab = "MISC"

            sorted_procedures[tab].append({
                "GUID": guid,
                "Name": name,
                "Procedures": procedures,
                "Runways": runways
            })

    return sorted_procedures if sorted_procedures else None


# Manage tabs
def switch_tab(tab_name):
    for widget in main_content.winfo_children():
        widget.destroy()

    if tab_name == "Charts":
        sidebar.pack(side="left", fill="y")
        update_charts()
    elif tab_name == "METAR":
        sidebar.pack_forget()
        update_metar()
    elif tab_name == "TAF":
        sidebar.pack_forget()
        update_taf()



# GUI
customtkinter.set_default_color_theme("blue")
app = customtkinter.CTk()
app.geometry("1080x720")
app.title("MSFS2024 Flight Planner API Demo")
app.iconbitmap("Logo.ico")

# Search bar and buttons
search_frame = customtkinter.CTkFrame(app, width=200, corner_radius=0)
search_frame.pack(side="top", anchor="ne", pady=10, padx=10)

search_entry = customtkinter.CTkEntry(search_frame, width=200, height=30, placeholder_text="Search Airport")
search_entry.pack(side="left", padx=5)

search_icon = Image.open("loupe.ico")
search_image = customtkinter.CTkImage(search_icon, size=(30, 30))

search_button = customtkinter.CTkButton(search_frame, width=30, height=30, image=search_image, text="", fg_color="white", hover_color="white", command=lambda: switch_tab("Charts"))
search_button.pack(side="left", padx=5)

# Updated tab_buttons to include TAF functionality
tab_buttons = [
    {"text": "Charts", "command": lambda: switch_tab("Charts")},
    {"text": "METAR", "command": lambda: switch_tab("METAR")},
    {"text": "TAF", "command": lambda: switch_tab("TAF")},
]

for tab in tab_buttons:
    button = customtkinter.CTkButton(
        search_frame,
        text=tab["text"],
        command=tab["command"],
        height=30,
        width=80
    )
    button.pack(side="left", padx=5)

# Chart Type Selector
sidebar = customtkinter.CTkFrame(app, width=200, corner_radius=0)
chart_buttons = [
    {"text": "Departure", "command": lambda: display_charts(chart_data, "Departure", main_content)},
    {"text": "Arrival", "command": lambda: display_charts(chart_data, "Arrival", main_content)},
    {"text": "Approach", "command": lambda: display_charts(chart_data, "Approach", main_content)},
    {"text": "Airport", "command": lambda: display_charts(chart_data, "Airport", main_content)},
    {"text": "MISC", "command": lambda: display_charts(chart_data, "MISC", main_content)},
]

for chart_btn in chart_buttons:
    button = customtkinter.CTkButton(sidebar, text=chart_btn["text"], command=chart_btn["command"], height=40)
    button.pack(pady=5, padx=10)

# Main Zone
main_content = customtkinter.CTkFrame(app)
main_content.pack(side="right", fill="both", expand=True, padx=10, pady=10)

chart_data = {}
threading.Thread(target=update_token, daemon=True).start()
app.mainloop()
