import uasyncio
import bluetooth
import struct
from machine import RTC

class RuuviTagApp:
    def __init__(self, target_mac="AA:BB:CC:DD:EE:FF"):
        self.target_addr = bytes(int(x, 16) for x in target_mac.split(':'))
        self.data = {"temp": "--.--"}
        self.last_update = "--:--:--"
        self.rtc = RTC()
        
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._ble_irq)

    def _ble_irq(self, event, data):
        if event == 5: # _IRQ_SCAN_RESULT
            addr_type, addr, adv_type, rssi, adv_data = data
            if addr == self.target_addr:
                self._parse_ruuvi_v5(bytes(adv_data))

    def _parse_ruuvi_v5(self, payload):
        try:
            idx = payload.find(b'\x99\x04\x05')
            if idx != -1:
                # Lämpötila: 16-bit signed, 0.005 kerrannaisena
                temp_raw = struct.unpack(">h", payload[idx + 3 : idx + 5])[0]
                
                if temp_raw != -32768:
                    # Tallennetaan lämpötila 2 desimaalilla
                    self.data["temp"] = "{:.2f}".format(temp_raw * 0.005)
                    
                    # Haetaan kellonaika RTC:stä päivityshetkellä
                    t = self.rtc.datetime()
                    self.last_update = "{:02d}:{:02d}:{:02d}".format(t[4], t[5], t[6])
        except Exception as e:
            print("Parserointivirhe:", e)

    async def update_data(self):
        while True:
            # Skannataan 5 sekuntia kerrallaan
            self.ble.gap_scan(5000, 30000, 30000)
            await uasyncio.sleep(10)

    def draw(self, fb):
        # 1. Otsikko keskelle
        otsikko = "RUUVITAG"
        # (84px - (8 merkkiä * 8px)) // 2  =>  (84 - 64) // 2 = 10
        otsikko_x = (84 - (len(otsikko) * 8)) // 2
        
        fb.text(otsikko, otsikko_x, 0, 1)
        fb.hline(0, 9, 84, 1)
        
        # 2. Lämpötila kahdella desimaalilla
        temp_str = self.data["temp"]
        # Lasketaan leveys: luku + aste-merkki (neliö) + C
        # 8px per merkki, 13px yhteensä asteelle ja C:lle
        kokonaisleveys = (len(temp_str) * 8) + 13
        alku_x = (84 - kokonaisleveys) // 2
        teksti_y = 18
        
        fb.text(temp_str, alku_x, teksti_y, 1)
        aste_x = alku_x + (len(temp_str) * 8) + 1
        fb.rect(aste_x, teksti_y - 2, 3, 3, 1) # Aste-merkki
        fb.text("C", aste_x + 5, teksti_y, 1)
        
        # 3. Päivitysaika alalaitaan
        #fb.hline(0, 35, 84, 1)
        #fb.text("PAIVITETTY:", 2, 38, 1) # Pieni otsikko alhaalla
        
        # Keskitytään vielä kellonaika aivan alas
        aika_x = (84 - (len(self.last_update) * 8)) // 2
        # Huom: Nokia 5110 on 48px korkea, teksti mahtuu juuri y-koordinaattiin 40
        fb.text(self.last_update, aika_x, 40, 1)


