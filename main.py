import network
import uasyncio
import urequests
from machine import Pin, SPI, RTC
import framebuf
import pcd8544
import ntptime
import time

from weather_app import WeatherApp
from clock_app import ClockApp
from news_app import NewsApp
from snake_app import SnakeApp

# --- ASETUKSET ---
WIFI_SSID = "MYWIFI"
WIFI_PASS = "mywifipasskey"
UTC_OFFSET = 2 * 3600 

# Näytön alustus
spi = SPI(1, baudrate=1000000, mosi=Pin(11), sck=Pin(10))
cs, dc, rst = Pin(18), Pin(16), Pin(17)
lcd = pcd8544.PCD8544(spi, cs, dc, rst)
lcd.contrast(0x3c)
buffer = bytearray(84 * 48 // 8)
fb = framebuf.FrameBuffer(buffer, 84, 48, framebuf.MONO_VLSB)

# Taustavalo
bl = Pin(13, Pin.OUT)
bl.value(1)

class PikOS:
    def __init__(self):
        self.active_app_name = "menu"
        self.apps = {
            "weather": WeatherApp(),
            "clock": ClockApp(),
            "news": NewsApp(),
            "snake": SnakeApp()
        }
        self.app_cycle = ["menu", "weather", "clock", "news"]
        self.autoplay = True
        self.ip = "0.0.0.0"
        self.tiny_font = {
            'A':[0x2,0x5,0x7,0x5,0x5],'B':[0x6,0x5,0x6,0x5,0x6],'C':[0x3,0x4,0x4,0x4,0x3],
            'D':[0x6,0x5,0x5,0x5,0x6],'E':[0x7,0x4,0x6,0x4,0x7],'F':[0x7,0x4,0x6,0x4,0x4],
            'G':[0x3,0x4,0x5,0x5,0x3],'H':[0x5,0x5,0x7,0x5,0x5],'I':[0x7,0x2,0x2,0x2,0x7],
            'J':[0x1,0x1,0x1,0x5,0x2],'K':[0x5,0x5,0x6,0x5,0x5],'L':[0x4,0x4,0x4,0x4,0x7],
            'M':[0x5,0x7,0x5,0x5,0x5],'N':[0x5,0x6,0x5,0x5,0x5],'O':[0x2,0x5,0x5,0x5,0x2],
            'P':[0x6,0x5,0x6,0x4,0x4],'R':[0x6,0x5,0x6,0x5,0x5],'S':[0x3,0x4,0x2,0x1,0x6],
            'T':[0x7,0x2,0x2,0x2,0x2],'U':[0x5,0x5,0x5,0x5,0x2],'V':[0x5,0x5,0x5,0x2,0x2],
            'W':[0x5,0x5,0x5,0x7,0x5],'X':[0x5,0x5,0x2,0x5,0x5],'Y':[0x5,0x5,0x2,0x2,0x2],
            'Z':[0x7,0x1,0x2,0x4,0x7],'0':[0x2,0x5,0x5,0x5,0x2],'1':[0x2,0x6,0x2,0x2,0x7],
            '2':[0x6,0x1,0x2,0x4,0x7],'3':[0x6,0x1,0x6,0x1,0x6],'4':[0x5,0x5,0x7,0x1,0x1],
            '5':[0x7,0x4,0x6,0x1,0x6],'6':[0x3,0x4,0x6,0x5,0x2],'7':[0x7,0x1,0x2,0x2,0x2],
            '8':[0x2,0x5,0x2,0x5,0x2],'9':[0x2,0x5,0x3,0x1,0x6],'.':[0x0,0x0,0x0,0x0,0x2],
            ':':[0x0,0x2,0x0,0x2,0x0],'-':[0x0,0x0,0x7,0x0,0x0],'/':[0x1,0x1,0x2,0x4,0x4],' ':[0x0,0x0,0x0,0x0,0x0]
        }

    def draw_tiny(self, text, x, y):
        curr_x = x
        for char in str(text):
            if char in self.tiny_font:
                bitmap = self.tiny_font[char]
                for row in range(5):
                    for col in range(3):
                        if (bitmap[row] >> (2 - col)) & 1:
                            fb.pixel(curr_x + col, y + row, 1)
            curr_x += 4

    def connect_wifi(self):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(WIFI_SSID, WIFI_PASS)
        retry = 20
        while not wlan.isconnected() and retry > 0:
            time.sleep(0.5)
            retry -= 1
        if wlan.isconnected():
            self.ip = wlan.ifconfig()[0]
            try:
                ntptime.settime()
                t = time.time() + UTC_OFFSET
                tm = time.localtime(t)
                RTC().datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
            except: pass

    async def fetch_auto_location(self):
        try:
            res = urequests.get("http://freeipapi.com")
            data = res.json()
            res.close()
            if "cityName" in data:
                self.apps["weather"].city = data["cityName"].replace('ä','a').replace('ö','o')
                uasyncio.create_task(self.apps["weather"].update_data())
        except: pass

    async def autoplay_task(self):
        idx = 0
        while True:
            if self.autoplay:
                current = self.app_cycle[idx]
                self.active_app_name = current
                wait = 5 if current == "menu" else 20
                for _ in range(wait):
                    if not self.autoplay: break
                    await uasyncio.sleep(1)
                idx = (idx + 1) % len(self.app_cycle)
            else:
                await uasyncio.sleep(1)

    async def serve_client(self, reader, writer):
        try:
            line = await reader.readline()
            request = line.decode()
            while True:
                h = await reader.readline()
                if h == b"" or h == b"\r\n": break

            # KOMENNOT
            # --- KOMENNOT ---
            if "/status" in request:
                writer.write('HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n')
                writer.write(str(self.apps["snake"].pituus))
                await writer.drain()
                await writer.wait_closed()
                return # Tärkeä: lopetetaan tähän
                
            elif "id=autoplay" in request:
                self.autoplay = not self.autoplay
                
            elif "city=" in request:
                try:
                    # 1. Erotetaan kaupunki GET-pyynnöstä
                    raw = request.split("city=")[1].split(" ")[0]
                    
                    # 2. Puretaan selaimen URL-koodaukset (UTF-8 %-koodit)
                    # Ä-kirjain (%C3%A4 tai %C3%84) ja Ö-kirjain (%C3%B6 tai %C3%96)
                    new_city = raw.replace("%C3%A4", "a").replace("%C3%84", "A")
                    new_city = new_city.replace("%C3%B6", "o").replace("%C3%96", "O")
                    
                    # 3. Puretaan välilyönnit ja muut perusmerkit
                    new_city = new_city.replace("+", " ").replace("%20", " ")
                    
                    # 4. Varmistetaan vielä suora korvaus (jos selain ei koodannut)
                    new_city = new_city.replace('ä', 'a').replace('Ä', 'A').replace('ö', 'o').replace('Ö', 'O')
                    
                    # Asetetaan kaupunki ja päivitetään
                    self.apps["weather"].city = new_city
                    uasyncio.create_task(self.apps["weather"].update_data())
                except Exception as e:
                    print("City encoding error:", e)

                
            elif "id=snake" in request:
                # Nollataan peli VAIN jos emme ole jo siellä (estää restartin)
                if self.active_app_name != "snake":
                    self.apps["snake"].reset_game()
                self.active_app_name = "snake"
                self.autoplay = False
                
            elif "dir/" in request:
                d = request.split("dir/")[1][0] # Poimitaan vain yksi merkki (w,a,s,d)
                self.apps["snake"].set_dir(d)
                
            elif "id=weather" in request: 
                self.active_app_name = "weather"; self.autoplay = False
            elif "id=clock" in request: 
                self.active_app_name = "clock"; self.autoplay = False
            elif "id=news" in request: 
                self.active_app_name = "news"; self.autoplay = False
            elif "id=menu" in request: 
                self.active_app_name = "menu"; self.autoplay = False


            # HTML VALINTA
            if self.active_app_name == "snake":
                html = self.get_snake_html()
            else:
                html = self.get_main_html()

            writer.write('HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n' + html)
            await writer.drain()
            await writer.wait_closed()
        except: pass

    def get_main_html(self):
        auto_txt = "ON" if self.autoplay else "OFF"
        auto_col = "#28a745" if self.autoplay else "#6c757d"
        city = self.apps["weather"].city
        
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body{{font-family:sans-serif;text-align:center;background:#eee;padding:10px;margin:0;}}
            .btn{{display:block;width:100%;max-width:300px;margin:10px auto;padding:18px;font-size:18px;background:#007bff;color:white;border:none;border-radius:12px;text-decoration:none;font-weight:bold;}}
            .btn-auto{{background:{auto_col};}}
            .btn-red{{background:#dc3545;}}
            .btn-green{{background:#28a745;}}
            
            /* LOMAKE SAMALLE RIVILLE */
            .city-form {{ 
                display: flex; 
                flex-direction: row; 
                justify-content: center; 
                align-items: center; 
                gap: 5px; 
                max-width: 300px; 
                margin: 0 auto 15px; 
            }}
            input {{ 
                flex: 1; 
                padding: 12px; 
                font-size: 16px; 
                border-radius: 10px; 
                border: 1px solid #ccc; 
                min-width: 0; /* Estää inputia puskemasta yli */
            }}
            .set-btn {{ 
                padding: 12px 20px; 
                background: #007bff; 
                color: white; 
                border: none; 
                border-radius: 10px; 
                font-weight: bold; 
                cursor: pointer;
                white-space: nowrap; 
            }}
        </style>
        </head><body>
            <h1>pikOS v1.8</h1>
            
            <a href="/app?id=autoplay" class="btn btn-auto">AUTOPLAY: {auto_txt}</a>
            
            <form action="/app" method="get" class="city-form">
                <input type="text" name="city" placeholder="{city}">
                <button type="submit" class="set-btn">SET</button>
            </form>
            
            <hr style="max-width:300px;">
            
            <a href="/app?id=snake" class="btn btn-green">PLAY SNAKE</a>
            <a href="/app?id=weather" class="btn">WEATHER</a>
            <a href="/app?id=clock" class="btn">CLOCK</a>
            <a href="/app?id=news" class="btn">NEWS</a>
            <a href="/app?id=menu" class="btn btn-green">INFO</a>
            
        </body></html>"""

    def get_snake_html(self):
        score = self.apps["snake"].pituus
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body {{ text-align: center; font-family: sans-serif; background: #fff; color: #333; touch-action: manipulation; margin: 0; padding: 10px; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #eee; }}
            .exit-btn {{ text-decoration: none; font-size: 24px; font-weight: bold; color: #fff; 
                        background: #dc3545; width: 40px; height: 40px; line-height: 40px; 
                        border-radius: 50%; display: inline-block; }}
            .score-box {{ font-size: 20px; font-weight: bold; color: #007bff; }}
            .grid {{ display: grid; grid-template-columns: repeat(3, 80px); gap: 15px; justify-content: center; margin-top: 40px; }}
            button {{ width: 80px; height: 80px; font-size: 35px; border-radius: 20px; border: 2px solid #007bff; 
                     background: #f8f9fa; color: #007bff; box-shadow: 0 4px 0 #0056b3; }}
            button:active {{ transform: translateY(4px); box-shadow: none; }}
        </style>
        </head><body>
            <div class="header">
                <a href="/app?id=menu" class="exit-btn">X</a>
                <div class="score-box">Pituus: <span id="s">{score}</span></div>
                <div style="width:40px"></div>
            </div>
            <div class="grid">
                <div></div><button onclick="go('w')">▲</button><div></div>
                <button onclick="go('a')">◀</button><button onclick="go('s')">▼</button><button onclick="go('d')">▶</button>
            </div>
            <script>
                function go(d) {{ fetch('/dir/' + d); }}
                // Päivitetään vain pisteruutu, ei koko sivua
                setInterval(async () => {{
                    try {{
                        let r = await fetch('/status');
                        let t = await r.text();
                        document.getElementById('s').innerText = t;
                    }} catch(e) {{}}
                }}, 2000);
            </script>
        </body></html>"""


    async def display_loop(self):
        while True:
            fb.fill(0)
            if self.active_app_name == "menu":
                fb.text("pikOS v1.7", 0, 0, 1)
                fb.hline(0, 9, 84, 1)
                self.draw_tiny("IP: " + self.ip, 0, 14)
                st = "AUTO: ON" if self.autoplay else "AUTO: OFF"
                self.draw_tiny(st, 0, 24)
                self.draw_tiny("READY", 0, 38)
            else:
                self.apps[self.active_app_name].draw(fb)
                #if self.autoplay: fb.pixel(82, 0, 1)
            lcd.data(buffer)
            await uasyncio.sleep_ms(100 if self.active_app_name == "snake" else 200)

async def main():
    os = PikOS()
    os.connect_wifi()
    await os.fetch_auto_location()
    for app in os.apps.values():
        uasyncio.create_task(app.update_data())
    uasyncio.create_task(uasyncio.start_server(os.serve_client, "0.0.0.0", 80))
    uasyncio.create_task(os.autoplay_task())
    await os.display_loop()

try:
    uasyncio.run(main())
except:
    pass


