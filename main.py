import network
import uasyncio
import urequests
import framebuf
import pcd8544
import ntptime
import time
import gc
import machine
from machine import Pin, SPI, RTC, ADC

from weather_app import WeatherApp
from clock_app import ClockApp
from news_app import NewsApp
from snake_app import SnakeApp
from ruuvitag_app import RuuviTagApp
#from iss_app import ISSApp

gc.collect() # Vapauttaa muistia

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

# Alustetaan lämpötila-anturi luokan ulkopuolella (pysyy globaalina)
temp_sensor = machine.ADC(4)

class PikOS:
    def __init__(self):
        # Määritellään RTC heti alussa
        self.rtc = machine.RTC()
        # 1. Luodaan sääsovellus ensin
        weather = WeatherApp()
        gc.collect()
        
        self.start_time = time.ticks_ms() # Lisää tämä uptimea varten
        self.active_app_name = "menu"
        self.apps = {
            "weather": weather,
            "clock": ClockApp(),
            "news": NewsApp(),
            "snake": SnakeApp(),
            "ruuvi": RuuviTagApp()
            #"iss": ISSApp(weather)
        }
        gc.collect()
        self.app_cycle = ["menu", "weather", "clock", "news", "ruuvi"] #"iss"]
        self.autoplay = True
        self.ip = "0.0.0.0"
        self.tiny_font = {
            'A':[0x2,0x5,0x7,0x5,0x5],'B':[0x6,0x5,0x6,0x5,0x6],'C':[0x3,0x4,0x4,0x4,0x3],
            'D':[0x6,0x5,0x5,0x5,0x6],'E':[0x7,0x4,0x6,0x4,0x7],'F':[0x7,0x4,0x6,0x4,0x4],
            'G':[0x3,0x4,0x5,0x5,0x3],'H':[0x5,0x5,0x7,0x5,0x5],'I':[0x7,0x2,0x2,0x2,0x7],
            'J':[0x1,0x1,0x1,0x5,0x2],'K':[0x5,0x5,0x6,0x5,0x5],'L':[0x4,0x4,0x4,0x4,0x7],
            'M':[0x5,0x7,0x5,0x5,0x5],'N':[0x5,0x7,0x7,0x5,0x5],'O':[0x2,0x5,0x5,0x5,0x2],
            'P':[0x6,0x5,0x6,0x4,0x4],'R':[0x6,0x5,0x6,0x5,0x5],'S':[0x3,0x4,0x2,0x1,0x6],
            'T':[0x7,0x2,0x2,0x2,0x2],'U':[0x5,0x5,0x5,0x5,0x2],'V':[0x5,0x5,0x5,0x2,0x2],
            'W':[0x5,0x5,0x5,0x7,0x5],'X':[0x5,0x5,0x2,0x5,0x5],'Y':[0x5,0x5,0x2,0x2,0x2],
            'Z':[0x7,0x1,0x2,0x4,0x7],'0':[0x2,0x5,0x5,0x5,0x2],'1':[0x2,0x6,0x2,0x2,0x7],
            '2':[0x6,0x1,0x2,0x4,0x7],'3':[0x6,0x1,0x6,0x1,0x6],'4':[0x5,0x5,0x7,0x1,0x1],
            '5':[0x7,0x4,0x6,0x1,0x6],'6':[0x3,0x4,0x6,0x5,0x2],'7':[0x7,0x1,0x2,0x2,0x2],
            '8':[0x2,0x5,0x2,0x5,0x2],'9':[0x2,0x5,0x3,0x1,0x6],'.':[0x0,0x0,0x0,0x0,0x2],
            ':':[0x0,0x2,0x0,0x2,0x0],'-':[0x0,0x0,0x7,0x0,0x0],'/':[0x1,0x1,0x2,0x4,0x4],' ':[0x0,0x0,0x0,0x0,0x0], '%': [0x5, 0x1, 0x2, 0x4, 0x5]
        }
        # Haetaan oletuskaupunki sääsovelluksesta
        self.current_city = weather.city
        
    def draw_startup_progress(self, percent, text):
        # Tyhjennetään puskuri
        # Oletetaan että fb, buffer ja lcd on määritelty PikOS-luokassa tai globaalisti
        fb.fill(0)
        
        # Otsikko
        fb.text("pikOS v1.8", 0, 0, 1)
        fb.hline(0, 9, 84, 1)
        
        # Latauspalkin kehys (keskitetty 64px leveä palkki)
        fb.rect(10, 22, 64, 10, 1)
        
        # Täytetään palkki
        fill_w = int((percent / 100) * 60)
        if fill_w > 0:
            fb.fill_rect(12, 24, fill_w, 6, 1)
            
        # Vaiheteksti (käytetään draw_tinyä, jos se on käytössä)
        # Jos ei ole, käytä fb.text:
        text_x = (84 - (len(text) * 8)) // 2
        if text_x < 0: text_x = 0
        fb.text(text, text_x, 38, 1)
        
        # Päivitetään fyysinen näyttö heti
        lcd.data(buffer)

        
    def get_finland_offset(self):
        # Haetaan nykyinen UTC-aika (NTP asetti tämän)
        now = time.time()
        year = time.localtime(now)[0]
        
        # Kesäaika alkaa maaliskuun viimeisenä sunnuntaina klo 01:00 UTC
        m_last = time.mktime((year, 3, 31, 1, 0, 0, 0, 0))
        m_wd = (time.localtime(m_last)[6] + 1) % 7
        dst_start = m_last - (m_wd * 86400)
        
        # Lokakuun viimeinen sunnuntai klo 01:00 UTC
        o_last = time.mktime((year, 10, 31, 1, 0, 0, 0, 0))
        o_wd = (time.localtime(o_last)[6] + 1) % 7
        dst_end = o_last - (o_wd * 86400)
        
        if dst_start <= now < dst_end:
            return 3 * 3600 # Kesäaika (UTC+3)
        return 2 * 3600     # Talviaika (UTC+2)
            
    def get_stats(self):
        # 1. Muisti
        gc.collect()
        mem_p = int((gc.mem_alloc() / (gc.mem_free() + gc.mem_alloc())) * 100)
        
        # 2. WiFi RSSI
        try:
            rssi = network.WLAN(network.STA_IF).status('rssi')
        except:
            rssi = 0
            
        # 3. Lämpötila (Pico 2 / RP2350 kaava)
        reading = temp_sensor.read_u16() * (3.3 / 65535)
        temp = 27 - (reading - 0.706) / 0.001721

        # 4. Uptime (sekuntia)
        uptime_sec = time.ticks_diff(time.ticks_ms(), self.start_time) // 1000
        
        return mem_p, rssi, temp, uptime_sec

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
        import gc
        gc.collect() # Varmistetaan maksimimuisti HTTPS-yhteydelle
        
        try:
            # Käytetään HTTPS-osoitetta suoraan välttääksemme redirect-hukan
            url = "https://free.freeipapi.com/api/json/"
            print("Haetaan sijaintia (HTTPS)...")
            
            # Timeout on tärkeä, jos HTTPS-kättely kestää
            res = urequests.get(url, timeout=15)
            data = res.json()
            res.close()
            
            # Poimitaan kaupunki ja koordinaatit
            city = data.get("cityName", "Kempele")
            lat = data.get("latitude")
            lon = data.get("longitude")
            
            # 1. Päivitetään Web UI:n placeholder-teksti heti
            self.current_city = city
            
            # 2. Päivitetään sääsovelluksen oletukset
            weather = self.apps["weather"]
            weather.city = city
            weather.lat = lat
            weather.lon = lon
            
            print(f"Sijainti asetettu: {city} ({lat}, {lon})")
            
        except Exception as e:
            print("Auto-location error (HTTPS):", e)
            # Jos HTTPS epäonnistuu muistipulaan, pidetään Kemijärvi oletuksena
        finally:
            gc.collect()


    async def autoplay_task(self):
        idx = 0
        while True:
            if self.autoplay:
                current = self.app_cycle[idx]
                self.active_app_name = current
                #wait = 5 if current == "menu" else 20
                wait = 20
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
            
            if "/screen.bmp" in request:
                writer.write('HTTP/1.1 200 OK\r\nContent-Type: image/bmp\r\nCache-Control: no-cache\r\n\r\n')
                writer.write(self.get_bmp_snapshot())
                await writer.drain()
                await writer.wait_closed()
                return
    
            elif "id=autoplay" in request:
                self.autoplay = not self.autoplay
                
            elif "city=" in request:
                try:
                    # 1. Erotetaan kaupunki GET-pyynnöstä
                    raw = request.split("city=")[1].split(" ")[0]
                    
                    # 2. Puhdistetaan koodaukset (kuten sinulla jo oli)
                    new_city = raw.replace("%C3%A4", "a").replace("%C3%84", "A")
                    new_city = new_city.replace("%C3%B6", "o").replace("%C3%96", "O")
                    new_city = new_city.replace("+", " ").replace("%20", " ")
                    new_city = new_city.replace('ä', 'a').replace('Ä', 'A').replace('ö', 'o').replace('Ö', 'O')
                    
                    # --- LISÄÄ TÄMÄ RIVI TÄHÄN ---
                    # Päivitetään placeholder-teksti heti tässä
                    self.current_city = new_city
                    
                    # Käynnistetään koordinaattien haku taustalla
                    uasyncio.create_task(self.apps["weather"].set_city(new_city))
                    
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
            elif "id=ruuvi" in request: 
                self.active_app_name = "ruuvi"; self.autoplay = False
            #elif "id=iss" in request: 
            #    self.active_app_name = "iss"; self.autoplay = False

            # HTML VALINTA
            if self.active_app_name == "snake":
                html = self.get_snake_html()
            else:
                html = self.get_main_html()

            # Lisätään Cache-Control ja Pragma otsikot tässä:
            response_headers = (
                'HTTP/1.1 200 OK\r\n'
                'Content-Type: text/html\r\n'
                'Cache-Control: no-cache, no-store, must-revalidate\r\n'
                'Pragma: no-cache\r\n'
                'Expires: 0\r\n'
                'Connection: close\r\n\r\n'
            )
            
            writer.write(response_headers + html)
            #writer.write('HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n' + html)
            await writer.drain()
            await writer.wait_closed()
        except: pass

    def get_main_html(self):
        auto_txt = "ON" if self.autoplay else "OFF"
        auto_col = "#28a745" if self.autoplay else "#6c757d"
        #city = self.apps["weather"].city
        city = self.current_city
        
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body{{font-family:sans-serif;text-align:center;background:#eee;padding:10px;margin:0;}}
            
            /* LIVE PREVIEW TYYLI */
            .preview {{ 
                width: 252px; height: 144px; /* 3x suurennos 84x48 koosta */
                /* border: 4px solid #333; background: #fff; */
                border: none;  
                image-rendering: pixelated; /* Pitää kuvan terävänä */
                margin: 10px auto; display: block; border-radius: 0px; padding: 25px; background-color: white;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }}

            .btn{{display:block;width:100%;max-width:300px;margin:10px auto;padding:18px;font-size:18px;background:#007bff;color:white;border:none;border-radius:12px;text-decoration:none;font-weight:bold;}}
            .btn-auto{{background:{auto_col};}}
            .btn-red{{background:#dc3545;}}
            .btn-green{{background:#28a745;}}
            
            .city-form {{ 
                display: flex; flex-direction: row; justify-content: center; 
                align-items: center; gap: 5px; max-width: 300px; margin: 0 auto 15px; 
            }}
            input {{ 
                flex: 1; padding: 12px; font-size: 16px; border-radius: 10px; 
                border: 1px solid #ccc; min-width: 0; 
            }}
            .set-btn {{ 
                padding: 12px 20px; background: #007bff; color: white; 
                border: none; border-radius: 10px; font-weight: bold; 
                cursor: pointer; white-space: nowrap; 
            }}
            .preview-container {{
                position: relative;
                width: 302px; /* 252px + 2*25px padding */
                margin: 10px auto;
            }}
            .loading-text {{
                position: absolute;
                top: 50%; left: 50%;
                transform: translate(-50%, -50%);
                font-weight: bold; color: #666;
                z-index: 0;
            }}
            #live {{
                position: relative;
                z-index: 1;
                transition: opacity 0.2s; /* Pehmeä häivytys */
            }}

        </style>
        </head><body>
            <h1>pikOS v1.8</h1>
            
            <!-- LIVE RUUTUKAAPPAUS -->
            <div class="preview-container">
                <div class="loading-text">LOADING...</div>
                <img id="live" class="preview" src="/screen.bmp"> 
            </div>


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
            <a href="/app?id=ruuvi" class="btn">RUUVITAG</a>
            <a href="/app?id=menu" class="btn">INFO</a>

            <script>
                const liveImg = document.getElementById('live');
                
                function refreshLive() {{
                    liveImg.src = '/screen.bmp?t=' + Date.now();
                }}

                // Piilotetaan kuva heti sivun latautuessa
                liveImg.style.opacity = '0';

                window.onload = () => {{
                    // Odotetaan 300ms että Pico ehtii piirtää, sitten ladataan kuva
                    setTimeout(() => {{
                        refreshLive();
                        liveImg.onload = () => {{ liveImg.style.opacity = '1'; }};
                    }}, 300);
                }};

                setInterval(refreshLive, 1500); // 1.5s päivitysväli säästää Picon tehoja

                // Piilotetaan kuva jos käyttäjä klikkaa mitä tahansa ohjausnappia
                document.querySelectorAll('.btn, .set-btn').forEach(btn => {{
                    btn.addEventListener('click', () => {{
                        liveImg.style.opacity = '0';
                    }});
                }});
            </script>

            
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
            
            /* LIVE RUUTU */
            .preview {{ 
                width: 252px; height: 144px; image-rendering: pixelated; 
                margin: 20px auto; display: block; border: 2px solid #eee; border-radius: 8px;
            }}

            .grid {{ display: grid; grid-template-columns: repeat(3, 80px); gap: 15px; justify-content: center; margin-top: 20px; }}
            button {{ width: 80px; height: 80px; font-size: 35px; border-radius: 20px; border: 2px solid #007bff; 
                     background: #f8f9fa; color: #007bff; box-shadow: 0 4px 0 #0056b3; cursor: pointer; }}
            button:active {{ transform: translateY(4px); box-shadow: none; }}
        </style>
        </head><body>
            <div class="header">
                <a href="/app?id=menu" class="exit-btn">X</a>
                <div class="score-box">Pituus: <span id="s">{score}</span></div>
                <div style="width:40px"></div>
            </div>

            <!-- NÄKYMÄ LAITTEEN RUUDULTA -->
            <img id="live" class="preview" src="/screen.bmp">

            <div class="grid">
                <div></div><button onclick="go('w')">▲</button><div></div>
                <button onclick="go('a')">◀</button><button onclick="go('s')">▼</button><button onclick="go('d')">▶</button>
            </div>

            <script>
                function go(d) {{ fetch('/dir/' + d); }}
                
                // Näppäimistötuki
                document.onkeydown = (e) => {{
                    let k = e.key.toLowerCase();
                    if(k=='arrowup'||k=='w') go('w');
                    if(k=='arrowdown'||k=='s') go('s');
                    if(k=='arrowleft'||k=='a') go('a');
                    if(k=='arrowright'||k=='d') go('d');
                }};

                // Päivitetään kuva ja pituus
                setInterval(async () => {{
                    document.getElementById('live').src = '/screen.bmp?t=' + Date.now();
                    try {{
                        let r = await fetch('/status');
                        let t = await r.text();
                        document.getElementById('s').innerText = t;
                    }} catch(e) {{}}
                }}, 500); // 400ms on hyvä kompromissi viiveen ja verkon kuormituksen välillä
            </script>
        </body></html>"""



    async def display_loop(self):
        while True:
            fb.fill(0)
            if self.active_app_name == "menu":
                #fb.text("pikOS v1.8", 0, 0, 1)
                #fb.hline(0, 9, 84, 1)
                #self.draw_tiny("IP: " + self.ip, 0, 14)
                #st = "AUTO: ON" if self.autoplay else "AUTO: OFF"
                #self.draw_tiny(st, 0, 24)
                #self.draw_tiny("READY", 0, 38)
                fb.text("pikOS v1.8", 0, 0, 1)
                fb.hline(0, 9, 84, 1)
                
                mem, rssi, temp, upt = self.get_stats()
                
                self.draw_tiny(f"IP: {self.ip}", 0, 12)
                self.draw_tiny(f"UPTIME: {upt} S", 0, 19)
                self.draw_tiny(f"MEM: {mem}% CPU: {int(temp)}C", 0, 26)
                self.draw_tiny(f"WIFI: {rssi} DBM", 0, 33)
                st = "AUTOPLAY: ON" if self.autoplay else "AUTOPLAY: OFF"
                self.draw_tiny(st, 0, 40)
                #fb.text(st, 0, 42, 1) # Isompi teksti pohjalle
            else:
                self.apps[self.active_app_name].draw(fb)
                #if self.autoplay: fb.pixel(82, 0, 1)
            lcd.data(buffer)
            await uasyncio.sleep_ms(100 if self.active_app_name == "snake" else 200)
            
    def get_bmp_snapshot(self):
        # Header (84x48, 1-bit)
        header = bytearray([
            0x42, 0x4D, 0x3E, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x3E, 0x00, 0x00, 0x00, 0x28, 0x00,
            0x00, 0x00, 0x54, 0x00, 0x00, 0x00, 0x30, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00
        ])
        
        row_size = 12
        bmp_data = bytearray(row_size * 48)
        global buffer
        
        # Positiivinen gap_fix (12) siirtää vasenta lohkoa oikealle päin
        # base_offset (20) siirtää koko kuvaa
        base_offset = 0
        gap_fix = 0

        for y in range(48):
            target_y = 47 - y
            row_start = target_y * row_size
            for x in range(84):
                if x < 32:
                    # Tämä siirtää vasemman puoliskon datan lukukohtaa
                    source_x = (x + base_offset + gap_fix) % 84
                else:
                    source_x = (x + base_offset) % 84
                
                byte_idx = (y // 8) * 84 + source_x
                bit_idx = y % 8

                if (buffer[byte_idx] >> bit_idx) & 1:
                    bmp_data[row_start + (x // 8)] |= (1 << (7 - (x % 8)))


        
        return header + bmp_data



    async def sync_time(self):
        global UTC_OFFSET
        try:
            import ntptime
            print("Synkronoidaan kello (NTP)...")
            ntptime.settime() # Asettaa Picon ajan UTC 0:ksi
            
            # Kutsutaan metodia käyttäen self. etuliitettä
            UTC_OFFSET = self.get_finland_offset()
            
            # Päivitetään RTC paikalliseen aikaan
            t = time.time() + UTC_OFFSET
            tm = time.localtime(t)
            
            # RTC format: (year, month, day, weekday, hours, minutes, seconds, subseconds)
            # tm: (year, month, mday, hour, minute, second, weekday, yearday)
            self.rtc.datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
            
            print("Aika päivitetty. Offset: {}h".format(UTC_OFFSET // 3600))
        except Exception as e:
            print("NTP virhe:", e)


async def main():
    # 1. Luodaan käyttöjärjestelmä-olio
    os_instance = PikOS() 
    
    # 2. Yhdistetään verkkoon
    os_instance.draw_startup_progress(10, "WIFI...")
    os_instance.connect_wifi()
    
    # 3. Synkronoidaan kello
    os_instance.draw_startup_progress(25, "NTP SYNC")
    await os_instance.sync_time()
    
    # 4. Haetaan sijainti
    os_instance.draw_startup_progress(40, "LOCATION")
    await os_instance.fetch_auto_location()
    
    # 5. Käynnistetään sovellukset PORRASTETUSTI
    apps_list = list(os_instance.apps.items())
    total = len(apps_list)
    
    for i, (name, app) in enumerate(apps_list):
        # Lasketaan prosentti välille 50% - 90%
        percent = 50 + int((i / total) * 40)
        os_instance.draw_startup_progress(percent, name.upper())
        
        uasyncio.create_task(app.update_data())
        await uasyncio.sleep(2) 
        gc.collect() 

    # 6. Käynnistetään palvelin ja autoplay
    os_instance.draw_startup_progress(95, "WEB SERVER")
    uasyncio.create_task(uasyncio.start_server(os_instance.serve_client, "0.0.0.0", 80))
    uasyncio.create_task(os_instance.autoplay_task())
    
    # 7. Valmis!
    os_instance.draw_startup_progress(100, "READY")
    await uasyncio.sleep(1) # Näytetään "READY" hetki
    
    print("PikOS v1.8 käynnissä.")
    await os_instance.display_loop()

try:
    uasyncio.run(main())
except Exception as e:
    print("Kriittinen virhe:", e)
    # machine.reset() # Voit ottaa tämän käyttöön, jos haluat automaattisen uudelleenkäynnistyksen

