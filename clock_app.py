from machine import RTC
import uasyncio

class ClockApp:
    def __init__(self):
        self.rtc = RTC()

    async def update_data(self):
        while True:
            # Kello ei tarvitse kovaa taustatyötä, pidetään taski elossa
            await uasyncio.sleep(1)

    def draw(self, fb):
        t = self.rtc.datetime() # (v, kk, pv, vpv, h, m, s, ms)
        
        # Suomenkieliset lyhenteet (vpv on indeksi 3)
        viikonpaivat = ["MAANANTAI", "TIISTAI", "KESKIVIIKKO", "TORSTAI", "PERJANTAI", "LAUANTAI", "SUNNUNTAI"]
        vpv_teksti = viikonpaivat[t[3]]
        
        # Keskitetään teksti laskemalla x-koordinaatti (84px leveys, merkki on 8px leveä)
        x_pos = (84 - (len(vpv_teksti) * 8)) // 2
        
        kello = "{:02d}:{:02d}:{:02d}".format(t[4], t[5], t[6])
        pvm = "{:02d}.{:02d}.{}".format(t[2], t[1], t[0])
        
        # Piirretään viikonpäivä ylös
        fb.text(vpv_teksti, x_pos, 0, 1)
        fb.hline(0, 9, 84, 1)
        
        # Kello ja päivämäärä
        fb.text(pvm, 2, 18, 1)
        fb.text(kello, 10, 35, 1)

