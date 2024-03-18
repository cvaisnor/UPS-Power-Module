import threading
import time
import os
import urllib

import Adafruit_SSD1306
import PIL.Image
import PIL.ImageFont
import PIL.ImageDraw

from http import server

from ups_display import ina219

from .utils import ip_address, power_mode, power_usage, cpu_usage, gpu_usage, memory_usage, disk_usage


class DisplayServer(server.BaseHTTPRequestHandler):
    
    def __init__(self, web_address ):
        super().__init__( web_address )

        adress = os.popen("i2cdetect -y -r 1 0x42 0x42 | egrep '42' | awk '{print $2}'").read()
        if(adress=='42\n'):
            self.ina = ina219.INA219(addr=0x42)
        else:
            self.ina = None
            
        self.display = Adafruit_SSD1306.SSD1306_128_32(rst=None, i2c_bus=1, gpio=1) 
        self.display.begin()
        self.display.clear()
        self.display.display()
        self.font = PIL.ImageFont.load_default()
        self.image = PIL.Image.new('1', (self.display.width, self.display.height))
        self.draw = PIL.ImageDraw.Draw(self.image)
        self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)
        self.stats_enabled = False
        self.stats_thread = None
        self.stats_interval = 1.0
        self.enable_stats()
    pass
        
    def _run_display_stats(self):
        Charge = False
        while self.stats_enabled:

            self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)

            # set IP address
            top = -2
            if ip_address('eth0') is not None:
                self.draw.text((4, top), 'IP: ' + str(ip_address('eth0')), font=self.font, fill=255)
            elif ip_address('wlan0') is not None:
                self.draw.text((4, top), 'IP: ' + str(ip_address('wlan0')), font=self.font, fill=255)
            else:
                self.draw.text((4, top), 'IP: not available')

            top = 6
            power_mode_str = power_mode()

            p = 0 

            if(self.ina != None):
                bus_voltage = self.ina.getBusVoltage_V()        # voltage on V- (load side)
                current = self.ina.getCurrent_mA()                # current in mA
                p = (bus_voltage - 6)/2.4*100
                if(p > 100):p = 100
                if(p < 0):p = 0
                if(current > 30):
                    Charge = not Charge
                else:
                    Charge = False

                if(Charge == False):
                    self.draw.text((600, -2), ' ', font=self.font, fill=255)
                else:
                    self.draw.text((120, -2), '*', font=self.font, fill=255)
                self.draw.text((4, top), power_mode_str + (" %.1fV")%bus_voltage + (" %.2fA")%(current/1000) + (" %2.0f%%")%p, font=self.font, fill=255)
            else:
                self.draw.text((4, top), 'MODE: ' + power_mode_str, font=self.font, fill=255)
            
            # set stats headers
            top = 14
            offset = 3 * 8
            headers = ['PWR', 'CPU', 'GPU', 'RAM', 'DSK']
            for i, header in enumerate(headers):
                self.draw.text((i * offset + 4, top), header, font=self.font, fill=255)

            # set stats fields
            top = 22
            power_watts = '%.1f' % p
            gpu_percent = '%02d%%' % int(round(gpu_usage() * 100.0, 1))
            cpu_percent = '%02d%%' % int(round(cpu_usage() * 100.0, 1))
            ram_percent = '%02d%%' % int(round(memory_usage() * 100.0, 1))
            disk_percent = '%02d%%' % int(round(disk_usage() * 100.0, 1))
            
            entries = [power_watts, cpu_percent, gpu_percent, ram_percent, disk_percent]
            for i, entry in enumerate(entries):
                self.draw.text((i * offset + 4, top), entry, font=self.font, fill=255)

            self.display.image(self.image)
            self.display.display()
    
            time.sleep(self.stats_interval)
        pass
    pass
            
    def enable_stats(self):
        # start stats display thread
        if not self.stats_enabled:
            self.stats_enabled = True
            self.stats_thread = threading.Thread(target=self._run_display_stats)
            self.stats_thread.start()
        pass
    pass
        
    def disable_stats(self):
        self.stats_enabled = False
        if self.stats_thread is not None:
            self.stats_thread.join()
        self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)
        self.display.image(self.image)
        self.display.display()
    pass

    def set_text(self, text):
        self.disable_stats()
        self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)
        
        lines = text.split('\n')
        top = 2
        for line in lines:
            self.draw.text((4, top), line, font=self.font, fill=255)
            top += 10
        
        self.display.image(self.image)
        self.display.display()
    pass

    def do_GET(self):
        if self.path == '/stats/on':
            self.enable_stats()
            return "stats enabled"
        elif self.path == '/stats/off':
            self.disable_stats()
            return "stats disabled"
        elif '/text/' in self.path :
            params = urllib.parse.parse_qs( self.path )
            
            text = ""
            
            if "text" in params :
                text = params[ "text" ][0]
            pass

            self.set_text( text )
            return f'set text: \n\n{text}'
        pass
    pass

pass # DisplayServer

if __name__ == '__main__':
    address = ('', 8000)
    server = DisplayServer( address )
    server.serve_forever()

