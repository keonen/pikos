import urequests
import uasyncio

class WeatherApp:
    def __init__(self):
        self.temp = "--.-"
        self.desc = "LOADING"
        self.city = "Helsinki"
        # OPENWEATHERMAP API KEY
        self.api_key = "723475755e65ab..."
        
        # TÄYSIN KORJATUT URL-OSOITTEET
        # {} merkit täytetään .format() metodilla update_data-funktiossa
        self.geo_url = "http://api.openweathermap.org/geo/1.0/direct?q={}&limit=1&appid={}"
        self.weather_url = "http://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&units=metric&appid={}"
        
        self.tiny_font = {
            'A':[0x2,0x5,0x7,0x5,0x5],'B':[0x6,0x5,0x6,0x5,0x6],'C':[0x3,0x4,0x4,0x4,0x3],
            'D':[0x6,0x5,0x5,0x5,0x6],'E':[0x7,0x4,0x6,0x4,0x7],'F':[0x7,0x4,0x6,0x4,0x4],
            'G':[0x3,0x4,0x5,0x5,0x3],'H':[0x5,0x5,0x7,0x5,0x5],'I':[0x7,0x2,0x2,0x2,0x7],
            'J':[0x1,0x1,0x1,0x5,0x2],'K':[0x5,0x5,0x6,0x5,0x5],'L':[0x4,0x4,0x4,0x4,0x7],
            'M':[0x5,0x7,0x5,0x5,0x5],'N':[0x5,0x6,0x5,0x5,0x5],'O':[0x2,0x5,0x5,0x5,0x2],
            'P':[0x6,0x5,0x6,0x4,0x4],'R':[0x6,0x5,0x6,0x5,0x5],'S':[0x3,0x4,0x2,0x1,0x6],
            'T':[0x7,0x2,0x2,0x2,0x2],'U':[0x5,0x5,0x5,0x5,0x2],'V':[0x5,0x5,0x5,0x2,0x2],
            'W':[0x5,0x5,0x5,0x7,0x5],'X':[0x5,0x5,0x2,0x5,0x5],'Y':[0x5,0x5,0x2,0x2,0x2],
            'Z':[0x7,0x1,0x2,0x4,0x7],' ':[0x0,0x0,0x0,0x0,0x0], '.':[0x0,0x0,0x0,0x0,0x2]
        }

    def draw_tiny(self, fb, text, x, y):
        curr_x = x
        for char in str(text).upper():
            if char in self.tiny_font:
                bitmap = self.tiny_font[char]
                for row in range(5):
                    for col in range(3):
                        if (bitmap[row] >> (2 - col)) & 1:
                            fb.pixel(curr_x + col, y + row, 1)
            curr_x += 4

    async def update_data(self):
        while True:
            try:
                # 1. Haetaan koordinaatit (Geocoding)
                safe_city = self.city.replace(" ", "%20")
                g_url = self.geo_url.format(safe_city, self.api_key)
                
                print("Geo-haku:", g_url)
                g_res = urequests.get(g_url)
                g_data = g_res.json()
                g_res.close()

                if isinstance(g_data, list) and len(g_data) > 0:
                    # Poimitaan ekan tuloksen lat ja lon
                    lat = g_data[0]["lat"]
                    lon = g_data[0]["lon"]
                    
                    # 2. Haetaan sää koordinaateilla
                    w_url = self.weather_url.format(lat, lon, self.api_key)
                    print("Sää-haku:", w_url)
                    
                    w_res = urequests.get(w_url)
                    w_data = w_res.json()
                    w_res.close()

                    if w_data.get("cod") == 200:
                        self.temp = str(round(w_data["main"]["temp"], 1))
                        self.desc = w_data["weather"][0]["main"]
                    else:
                        self.temp = "Err"
                        self.desc = "WEATHER API ERR"
                else:
                    self.temp = "???"
                    self.desc = "CITY NOT FOUND"

            except Exception as e:
                print("Weather update failed:", e)
                self.temp = "Err"
                self.desc = "NET ERROR"
            
            await uasyncio.sleep(600)

    def draw(self, fb):
        fb.text("WEATHER", 15, 0, 1)
        fb.hline(0, 9, 84, 1)
        
        fb.text(self.city.upper()[:10], 0, 12, 1)
        self.draw_tiny(fb, self.desc, 0, 22)
        
        temp_str = f"{self.temp}"
        fb.text(temp_str, 5, 35, 1)
        
        x_pos = 5 + (len(temp_str) * 8) + 1
        fb.rect(x_pos, 34, 3, 3, 1)
        fb.text("C", x_pos + 5, 35, 1)

