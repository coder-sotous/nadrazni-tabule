import flet as ft
import requests
from bs4 import BeautifulSoup

def main(page: ft.Page):
    page.title = "Nádražní tabule"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20

    # Vstup pro kód stanice
    station_key = ft.TextField(label="Kód stanice (např. 1919)", value="1919", width=250)
    
    # Seznam pro výsledky
    result_list = ft.ListView(expand=True, spacing=10)

    def get_data(e):
        result_list.controls.clear()
        result_list.controls.append(ft.Text("Načítám data...", color="yellow"))
        page.update()
        
        # Logika: Odjezdy vs Příjezdy (na základě tvého zjištění)
        # Tab 0 = Odjezdy, Tab 1 = Příjezdy
        base_url = f"https://provoz.spravazeleznic.cz/tabule/Pages/StationTable.aspx?Key={station_key.value}"
        
        if tabs.selected_index == 1:
            url = f"{base_url}&Arr=1"
        else:
            url = f"{base_url}&Mode=D"
        
        try:
            r = requests.get(url)
            soup = BeautifulSoup(r.text, 'html.parser')
            table = soup.find('table', {'class': 'dxbs-table'})
            
            result_list.controls.clear()
            
            if table:
                rows = table.find_all('tr')
                # Projdeme řádky, vynecháme hlavičku (první řádek)
                for row in rows[1:]:
                    cols = row.find_all('td')
                    # Spojíme všechny texty ze sloupců pro přehlednost
                    radek_text = " | ".join([c.text.strip() for c in cols if c.text.strip()])
                    
                    if radek_text:
                        result_list.controls.append(
                            ft.Container(
                                content=ft.Text(radek_text, size=14),
                                padding=10,
                                border=ft.border.all(1, ft.colors.WHITE24),
                                border_radius=5
                            )
                        )
            else:
                result_list.controls.append(ft.Text("Tabulka nenalezena. Zkontroluj kód stanice.", color="red"))
        except Exception as ex:
            result_list.controls.append(ft.Text(f"Chyba spojení: {ex}", color="red"))
        
        page.update()

    # Přepínací karty
    tabs = ft.Tabs(
        selected_index=0,
        on_change=get_data,
        tabs=[
            ft.Tab(text="Odjezdy"),
            ft.Tab(text="Příjezdy"),
        ]
    )

    page.add(
        ft.Text("Online Tabule SŽ", size=25, weight="bold"),
        station_key,
        ft.ElevatedButton("Načíst / Aktualizovat", on_click=get_data),
        tabs,
        result_list
    )

if __name__ == "__main__":
    # Takhle se to spustí správně na serveru
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)