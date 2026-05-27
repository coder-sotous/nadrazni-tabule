import flet as ft
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import asyncio
from datetime import datetime, timedelta
import os
import re

def najdi_kod_stanice(nazev_stanice):
    """Pomocná funkce pro vyhledání unikátního kódu stanice na webu SŽ."""
    if not nazev_stanice:
        return None
    nazev_stanice = nazev_stanice.strip()
    prvni_pismeno = nazev_stanice[0].upper()
    if len(nazev_stanice) > 1 and nazev_stanice[:2].upper() == "CH":
        prvni_pismeno = "CH"
        
    url = f"https://provoz.spravazeleznic.cz/tabule/Pages/StationList.aspx?Key={prvni_pismeno}"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "StationTable.aspx" in a['href']:
                if a.text.strip().lower() == nazev_stanice.lower():
                    parsed_url = urlparse(a['href'])
                    params = parse_qs(parsed_url.query)
                    if 'Key' in params: return params['Key'][0]
        for a in soup.find_all('a', href=True):
            if "StationTable.aspx" in a['href']:
                if nazev_stanice.lower() in a.text.strip().lower():
                    parsed_url = urlparse(a['href'])
                    params = parse_qs(parsed_url.query)
                    if 'Key' in params: return params['Key'][0]
    except:
        pass
    return None

async def main(page: ft.Page):
    page.title = "Nádražní tabule SŽ"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 15
    
    current_station_key = None
    all_trains_data = []
    blinking_containers = []

    # --- UI KOMPONENTY ---
    station_input = ft.TextField(
        label="Název stanice (např. Kladno, Ostrava...)", 
        value="Kladno", 
        expand=True
    )
    
    status_text = ft.Text("Aplikace připravena.", color="grey", size=12)
    smer_header_text = ft.Text("Cílová stanice", expand=True, weight="bold", color="amber")

    # Kontejner pro výluky a varování (NAD TABULKOU)
    notices_container = ft.Column(spacing=5, visible=False)

    # PEVNÉ GRAFICKÉ ZÁHLAVÍ
    table_header = ft.Container(
        content=ft.Row([
            ft.Text("Čas", width=60, weight="bold", color="amber"),
            ft.Text("Vlak", width=160, weight="bold", color="amber"), # Zvětšeno pro "Os 9826 ČD"
            ft.Text("Linka", width=70, weight="bold", color="amber"),
            smer_header_text,
            ft.Text("Zpoždění", width=90, weight="bold", color="amber", text_align="right"),
        ]),
        padding=ft.padding.only(left=15, right=15, top=12, bottom=12),
        bgcolor=ft.colors.BLACK38,
        border_radius=6,
        border=ft.border.all(1, ft.colors.WHITE10),
        visible=False
    )
    
    result_list = ft.ListView(expand=True, spacing=6)

    # --- LOGIKA ZOBRAZENÍ A GRAFIKY ---
    def update_display():
        blinking_containers.clear()
        result_list.controls.clear()
        now = datetime.now()

        for t in all_trains_data:
            vlak_up = t["druh"].upper()
            je_odjezd = (tabs.selected_index == 0)
            malo_casu = False

            # Výpočet blikání pro odjezdy
            if je_odjezd:
                try:
                    h, m = map(int, t["cas"].split(":"))
                    cas_vlaku = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    zpozdeni_min = int(t["zpozdeni"]) if t["zpozdeni"].isdigit() else 0
                    skutecny_odjezd = cas_vlaku + timedelta(minutes=zpozdeni_min)
                    
                    if (skutecny_odjezd - now).total_seconds() < -43200:
                        skutecny_odjezd += timedelta(days=1)
                        
                    zbyva_minut = (skutecny_odjezd - now).total_seconds() / 60.0

                    limit = 0
                    if vlak_up.startswith("OS") or vlak_up.startswith("SP") or t["is_bus"]:
                        limit = 1
                    elif vlak_up.startswith("R"):
                        limit = 2
                    elif any(vlak_up.startswith(x) for x in ["IC", "EC", "EX", "EN", "SC", "RJ"]):
                        limit = 3

                    if 0 <= zbyva_minut <= limit:
                        malo_casu = True
                except:
                    pass

            # Sestavení textu pro sloupec VLAK (Druh + Číslo + Dopravce)
            vlak_display = f"{t['druh']} {t['cislo']} {t['dopravce']}".strip()
            
            # Sestavení textu pro sloupec LINKA
            if t["is_bus"]:
                linka_display = t["linka"] if t["linka"] else "BUS"
                if linka_display != "BUS" and not linka_display.upper().startswith("X"):
                    linka_display = f"X{linka_display}"
                
                vlak_color = ft.colors.CYAN_200
                linka_color = ft.colors.CYAN_400
                row_bg = ft.colors.BLACK45
                row_border = ft.border.all(1, ft.colors.CYAN_700)
            else:
                linka_display = t["linka"] if t["linka"] else "-"
                linka_color = ft.colors.WHITE70
                row_bg = ft.colors.SURFACE_VARIANT
                row_border = ft.border.all(1, ft.colors.TRANSPARENT)
                
                if vlak_up.startswith("OS") or vlak_up.startswith("SP"):
                    vlak_color = ft.colors.GREEN_ACCENT_400
                elif any(vlak_up.startswith(x) for x in ["R", "IC", "EC", "EX", "EN", "SC", "RJ"]):
                    vlak_color = ft.colors.ORANGE_ACCENT_700
                else:
                    vlak_color = ft.colors.WHITE

            if t["zpozdeni"] == "0" or not t["zpozdeni"]:
                zpozdeni_text = "Včas"
                zpozdeni_color = ft.colors.GREEN_400
            else:
                zpozdeni_text = f"+{t['zpozdeni']} min"
                zpozdeni_color = ft.colors.RED_400

            # KONEČNĚ SPRÁVNÉ A BEZPEČNÉ ZAROVNÁNÍ
            row_container = ft.Container(
                content=ft.Row([
                    ft.Text(t["cas"], width=60, weight="bold", size=14),
                    ft.Text(vlak_display, width=160, color=vlak_color, weight="bold", size=14),
                    ft.Text(linka_display, width=70, color=linka_color, weight="bold", size=14),
                    ft.Text(t["smer"], expand=True, weight="w500", size=14),
                    ft.Text(zpozdeni_text, width=90, color=zpozdeni_color, weight="bold", text_align="right", size=14),
                ]),
                padding=ft.padding.only(left=15, right=15, top=10, bottom=10),
                bgcolor=row_bg,
                border_radius=5,
                border=row_border
            )

            if malo_casu:
                blinking_containers.append({
                    "container": row_container,
                    "orig_bg": row_bg
                })

            result_list.controls.append(row_container)

        if not all_trains_data:
            result_list.controls.append(ft.Text("Žádná data k zobrazení.", color="grey", size=14))
            
        page.update()

    # --- LOGIKA STAHOVÁNÍ DATA ---
    async def get_data(e=None, is_auto=False):
        nonlocal current_station_key, all_trains_data
        
        if not is_auto:
            table_header.visible = False
            notices_container.visible = False
            notices_container.controls.clear()
            all_trains_data = []
            result_list.controls.clear()
            result_list.controls.append(ft.Text("Načítám data z informačního systému...", color="yellow"))
            page.update()

        smer_header_text.value = "Výchozí stanice" if tabs.selected_index == 1 else "Cílová stanice"
        search_input = station_input.value.strip()
        if not search_input: return

        if not current_station_key:
            if search_input.isdigit():
                current_station_key = search_input
            else:
                status_text.value = "Vyhledávám stanici v registru SŽ..."
                page.update()
                current_station_key = await asyncio.to_thread(najdi_kod_stanice, search_input)

        if not current_station_key:
            result_list.controls.clear()
            result_list.controls.append(ft.Text(f"Stanice '{search_input}' nebyla nalezena.", color="red"))
            status_text.value = "Chyba: Stanice nenalezena."
            page.update()
            return

        base_url = f"https://provoz.spravazeleznic.cz/tabule/Pages/StationTable.aspx?Key={current_station_key}"
        url = f"{base_url}&Arr=1" if tabs.selected_index == 1 else f"{base_url}&Mode=D"

        try:
            status_text.value = "Stahuji aktuální hlášení..."
            page.update()
            
            r = await asyncio.to_thread(requests.get, url, {"timeout": 10})
            soup = BeautifulSoup(r.text, 'html.parser')
            table = soup.find('table', {'class': 'dxbs-table'})
            
            parsed_rows = []
            notices_list = []
            
            if table:
                # 1. Nejdřív projdeme VŠECHNY řádky a vytáhneme čisté výluky/oznámení
                for row in table.find_all('tr'):
                    cells = row.find_all('td')
                    # Výlukový řádek na SŽ má buď sloučený colspan, nebo text přes celou šířku
                    if len(cells) == 1 or (row.text.strip() and not any(re.match(r'^\d{1,2}:\d{2}$', c.text.strip()) for c in cells)):
                        txt = re.sub(r'\s+', ' ', row.text.strip())
                        if txt and "včas" not in txt.lower() and "čas" not in txt.lower() and "druh" not in txt.lower():
                            if txt not in notices_list:
                                notices_list.append(txt)

                # 2. Mapování sloupců pro vlaky podle záhlaví
                desktop_headers = []
                for th in table.find_all('th'):
                    if any(cls in th.get('class', []) for cls in ['d-md-none', 'd-sm-none', 'd-xs-none', 'visible-xs']):
                        continue
                    desktop_headers.append(th)

                col_mapping = {}
                for idx, th in enumerate(desktop_headers):
                    th_text = th.text.strip().lower()
                    if "čas" in th_text: col_mapping["cas"] = idx
                    elif "druh" in th_text: col_mapping["druh"] = idx
                    elif "číslo" in th_text: col_mapping["cislo"] = idx
                    elif "linka" in th_text: col_mapping["linka"] = idx
                    elif "dopravce" in th_text: col_mapping["dopravce"] = idx
                    elif "stanice" in th_text or "směr" in th_text: col_mapping["smer"] = idx
                    elif "zpožd" in th_text or "poznám" in th_text: col_mapping["zpozdeni"] = idx

                # 3. Zpracování samotných vlaků
                for row in table.find_all('tr')[1:]:
                    desktop_cols = []
                    for td in row.find_all('td'):
                        if any(cls in td.get('class', []) for cls in ['d-md-none', 'd-sm-none', 'd-xs-none', 'visible-xs']):
                            continue
                        desktop_cols.append(td)
                    
                    if not desktop_cols:
                        continue

                    # Kontrola, zda řádek obsahuje platný čas (např. 14:35) -> je to vlak
                    is_train_row = False
                    if "cas" in col_mapping and col_mapping["cas"] < len(desktop_cols):
                        cas_text = desktop_cols[col_mapping["cas"]].text.strip()
                        if re.match(r'^\d{1,2}:\d{2}$', cas_text):
                            is_train_row = True

                    if not is_train_row:
                        continue

                    # Bezpečné vytahování hodnot indexů
                    def ziskej_hodnotu(klic, vychozi="-"):
                        if klic in col_mapping and col_mapping[klic] < len(desktop_cols):
                            val = desktop_cols[col_mapping[klic]].text.strip()
                            return val if val else vychozi
                        return vychozi

                    cas = ziskej_hodnotu("cas")
                    vlak_druh = ziskej_hodnotu("druh")
                    vlak_cislo = ziskej_hodnotu("cislo")
                    linka = ziskej_hodnotu("linka", vychozi="")
                    dopravce = ziskej_hodnotu("dopravce", vychozi="")
                    smer = ziskej_hodnotu("smer")
                    
                    zpozdeni_raw = ziskej_hodnotu("zpozdeni", vychozi="0")
                    if "včas" in zpozdeni_raw.lower() or zpozdeni_raw == "0":
                        zpozdeni_min = "0"
                    else:
                        digits = "".join(c for c in zpozdeni_raw if c.isdigit())
                        zpozdeni_min = digits if digits else "0"
                        
                    is_bus = False
                    if any(x in vlak_druh.lower() for x in ["bus", "nbus", "autobus"]) or \
                       any(x in zpozdeni_raw.lower() for x in ["bus", "nad", "autobus"]):
                        is_bus = True

                    parsed_rows.append({
                        "cas": cas,
                        "druh": vlak_druh,
                        "cislo": vlak_cislo,
                        "linka": linka,
                        "dopravce": dopravce,
                        "smer": smer,
                        "zpozdeni": zpozdeni_min,
                        "is_bus": is_bus
                    })
                        
                all_trains_data = parsed_rows
                table_header.visible = True
                
                # Zobrazení nalezených výluk NAD TABULKOU
                notices_container.controls.clear()
                if notices_list:
                    notices_container.visible = True
                    for notice in notices_list:
                        notices_container.controls.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color=ft.colors.AMBER_A400, size=18),
                                    ft.Text(notice, color=ft.colors.AMBER_100, size=13, expand=True, weight="w500")
                                ]),
                                padding=12,
                                bgcolor=ft.colors.with_opacity(0.15, ft.colors.AMBER_900),
                                border=ft.border.all(1, ft.colors.with_opacity(0.4, ft.colors.AMBER_400)),
                                border_radius=6
                            )
                        )
                else:
                    notices_container.visible = False

                cas_aktualizace = datetime.now().strftime("%H:%M:%S")
                status_text.value = f"Aktualizováno: {cas_aktualizace} (Auto-obnova zapnuta)"
            else:
                all_trains_data = []
                table_header.visible = False
                notices_container.visible = False
                result_list.controls.clear()
                result_list.controls.append(ft.Text("Pro tuto stanici momentálně nejsou hlášeny žádné spoje.", color="orange"))
                status_text.value = "Stanice bez provozu."
        except Exception as ex:
            status_text.value = "Chyba sítě: Aktualizace selhala."
            if not is_auto:
                result_list.controls.clear()
                result_list.controls.append(ft.Text(f"Chyba spojení: {ex}", color="red"))

        update_display()

    async def manual_search(e):
        nonlocal current_station_key
        current_station_key = None
        await get_data()

    async def auto_refresh_worker():
        while True:
            await asyncio.sleep(30)
            if current_station_key:
                await get_data(is_auto=True)

    async def blink_worker():
        blink_state = False
        while True:
            await asyncio.sleep(0.5)
            blink_state = not blink_state
            if blinking_containers:
                for item in blinking_containers:
                    c = item["container"]
                    if blink_state:
                        c.bgcolor = ft.colors.RED_900
                    else:
                        c.bgcolor = item["orig_bg"]
                page.update()

    # --- SESTAVENÍ STRÁNKY ---
    tabs = ft.Tabs(
        selected_index=0,
        on_change=lambda e: page.run_task(get_data),
        tabs=[ft.Tab(text="Odjezdy"), ft.Tab(text="Příjezdy")]
    )

    page.add(
        ft.Row([
            ft.Text("Informační systém SŽ", size=22, weight="bold", color="amber"),
            ft.Icon(ft.icons.CELL_WIFI, color="green", size=18)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        
        ft.Row([
            station_input,
            ft.ElevatedButton("Vyhledat", on_click=manual_search, height=50)
        ]),
        
        ft.Divider(height=10, color="transparent"),
        tabs,
        ft.Divider(height=10, color="transparent"),
        
        # Blesková upozornění / výluky jsou spolehlivě nahoře
        notices_container,
        
        ft.Divider(height=5, color="transparent"),
        table_header,
        result_list,
        ft.Divider(height=5),
        ft.Row([status_text], alignment=ft.MainAxisAlignment.CENTER)
    )

    page.run_task(auto_refresh_worker)
    page.run_task(blink_worker)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8550))
   
    # TOTO JE KLÍČOVÉ: 
    # view=ft.AppView.WEB_BROWSER zajistí, že se nic neotevírá v okně.
    # host="0.0.0.0" zajistí, že server bude naslouchat externím požadavkům.
    ft.app(
        target=main, 
        view=ft.AppView.WEB_BROWSER, 
        port=port, 
        host="0.0.0.0"
    )