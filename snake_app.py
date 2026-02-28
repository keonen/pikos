import framebuf
import random
import uasyncio

class SnakeApp:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.mato = [(42, 24)] 
        self.suunta = (1, 0)
        self.pituus = 5
        self.omena = (random.randint(5, 78), random.randint(5, 42))
        self.nopeus = 0.07 

    async def update_data(self):
        while True:
            # Peli liikkuu vain jos se on aktiivinen (tämä hoituu main_loopissa)
            await uasyncio.sleep(1)

    def set_dir(self, d):
        if d == 'w' and self.suunta != (0, 1): self.suunta = (0, -1)
        elif d == 's' and self.suunta != (0, -1): self.suunta = (0, 1)
        elif d == 'a' and self.suunta != (1, 0): self.suunta = (-1, 0)
        elif d == 'd' and self.suunta != (-1, 0): self.suunta = (1, 0)

    def draw(self, fb):
        # Laske uusi pää
        paa_x, paa_y = self.mato[0]
        uusi_x = (paa_x + self.suunta[0]) % 84
        uusi_y = (paa_y + self.suunta[1]) % 48
        uusi_paa = (uusi_x, uusi_y)
        
        self.mato.insert(0, uusi_paa)
        
        # Omenan syönti
        if abs(uusi_x - self.omena[0]) < 3 and abs(uusi_y - self.omena[1]) < 3:
            self.pituus += 3
            self.omena = (random.randint(5, 78), random.randint(5, 42))
        
        if len(self.mato) > self.pituus:
            self.mato.pop()
            
        # Piirto
        fb.fill(0)
        fb.rect(self.omena[0]-1, self.omena[1]-1, 3, 3, 1) # Omena
        for seg in self.mato:
            fb.rect(seg[0]-1, seg[1]-1, 3, 3, 1) # Mato

