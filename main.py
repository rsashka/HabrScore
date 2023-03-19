# Read about program at https://habr.com/ru/post/723334/
# Source at https://github.com/rsashka/HabrScore

USER = 'rsashka'
WIFI_SSID = ''
WIFI_PASS = ''
TIMEZONE_SEC = 10800
QUERY_SEC = 20

import os
import sys
import network
import time
import ntptime
import ussl
import usocket
import gc
import machine

# Query Habr and parse response

def habr_query(user, marks):
    
    result = dict(marks)
    for key in marks:
        result[key] = None

    try:
        url = 'https://habr.com/ru/users/'+user+'/posts/'
        _, _, host, path = url.split('/', 3)


        # copy & paste from urequests
        s = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
        ai = usocket.getaddrinfo(host, 443, 0, usocket.SOCK_STREAM)
        ai = ai[0]
        s = usocket.socket(ai[0], usocket.SOCK_STREAM, ai[2])
        s.connect(ai[-1])
        s = ussl.wrap_socket(s, server_hostname=host)

        s.write(bytes('GET /%s HTTP/1.0\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))
        data = None

        while True:
            # Read small chunks because there is not enough RAM for readline()
            temp = s.read(1024)
            if (data is not None):
                data = temp
                temp = s.read(1024)
                data += temp
            else:
                # First reading
                data = b''
                continue 

            if data:
                # We are looking for only the necessary keys as substrings
                for key in marks:
                    
                    # The key is looked up only once
                    if (result[key] is not None):
                        continue
                    
                    start = data.find(marks[key])
                    if (start == -1):
                        continue
                    
                    # Get data between angle brackets
                    pos = data.find(b">", start)
                    end = data.find(b"<", pos)
                    if (pos>0 and end>0):
                        value = data[pos:end]
                        result[key] = value.decode().strip(' \n\t\r><');
                
            else:
                # End of data
                break
    except:
        print('\nBegin machine.soft_reset()\n')
        # Software reset and restart MicroPython
        machine.soft_reset()
    
    return result


# Output screet on the EP-0164 (https://aliexpress.ru/item/1005004743550177.html?sku_id=12000030313984981)

import machine
from micropython import const
from ili934xnew import ILI9341, color565

import glcdfont
import tt14
import tt24
import tt32
from random import randint 


SCR_WIDTH = const(320)
SCR_HEIGHT = const(240)
SCR_ROT = const(3)

#fonts = [glcdfont,tt14,tt24,tt32]

spi = machine.SPI(
    0,
    baudrate=40000000,
    miso=machine.Pin(4),
    mosi=machine.Pin(7),
    sck=machine.Pin(6))
print(spi)



display = ILI9341(
    spi,
    cs=machine.Pin(13),
    dc=machine.Pin(15),
    rst=machine.Pin(14),
    w=SCR_WIDTH,
    h=SCR_HEIGHT,
    r=SCR_ROT)

update_screen = True
CLR_BG = color565(255, 255, 255)

def message(msg, msg2=None, clr_txt=color565(0, 0, 0), clr_bg=CLR_BG):
    update_screen = True    
    display.set_color(color565(0, 0, 0), clr_bg)
    display.erase()

    display.set_color(clr_txt, clr_bg)
    display.set_pos(15,110)
    display.set_font(tt32)
    display.print(msg)
    
    if(msg2):
        display.set_pos(15,150)
        display.set_font(tt24)
        display.print(msg2)


def error(msg, msg2=None):
    message(msg, msg2, color565(255, 0, 0))
    
def status(msg):
    display.fill_rectangle(0, 220, SCR_WIDTH, 30, CLR_BG)
    display.set_color(color565(100, 100, 100), CLR_BG)
    display.set_pos(5,223)
    display.set_font(tt14)
    display.print(msg)






res = None
print(os.uname());

# Print title
sync_done = False
last_query = time.time()
update_screen = True
counter = 0;



# Main loop
led = machine.Pin(0, machine.Pin.OUT)
wlan = network.WLAN(network.STA_IF)
while(True):

    led.value(not led.value())
    
    wlan.active(True)
    if(not wlan.isconnected()):
        status('Connect to WiFi ...')
        #print(wlan.scan())

        start_s = time.time()
        wlan.connect(WIFI_SSID, WIFI_PASS)
        while not wlan.isconnected():
            
            if (time.time() - start_s) > 5:
                error('WiFi connection error!', 'Check SSID and password.')
                time.sleep(1)
                counter+=1

                if(counter > 10):
                    error('Performing a hard reboot!')
                    time.sleep(2)
                    # Hardware reset
                    machine.reset()

            wlan.active(True)
            time.sleep_ms(500)
            wlan.connect(WIFI_SSID, WIFI_PASS)

    print(wlan.ifconfig())
    #print(wlan.status())

    if(not sync_done):
        status('Sync local time ...')
        try:
            print("Local time before synchronization：%s" %str(time.localtime()))
            ntptime.time()
            print("Local time after synchronization：%s" %str(time.localtime()))
            sync_done = True
        except:
            error('Error syncing time')
            print("Error syncing time")
            time.sleep(1)

    # Search anchors in html page
    query = {
        # For user
        'KARMA': b'tm-karma__votes',
        'SCORE': b'tm-votes-lever__score-counter tm-votes-lever__score-counter tm-votes-lever__score-counter_rating',
        # For article
        'VIEWS': b'class="tm-icon-counter__value',
        'VOTES': b'class="tm-votes-meter__value tm-votes-meter__value',
        'BOOKMARK': b'bookmarks-button__counter',
        'COMMENTS': b'tm-article-comments-counter-link__value',    
    }


    HEAD_BGR = color565(10, 0, 0)
    if(update_screen):
        display.set_color(color565(0, 0, 0), CLR_BG)
        display.erase()
        
        display.fill_rectangle(0, 0, SCR_WIDTH, 40, HEAD_BGR)
        display.set_color(color565(255, 255, 255), HEAD_BGR)
        display.set_pos(10,4)
        display.set_font(tt32)
        display.print("HabrScore")
        update_screen = False

    if ((res is None) or (time.time() - last_query > QUERY_SEC)):
            
        last_query = time.time()
        status('Request about user "@'+USER+'"')

        new = habr_query(USER, query)
        if(new['SCORE'] and new['KARMA']):
            res = new
            status('Request completd')
        else:
            status('Request fail. Use old data')

        #res = {'VOTES': '+1', 'BOOKMARK': '14', 'KARMA': '96', 'SCORE': '52.1', 'COMMENTS': '29', 'VIEWS': '4.2K'} #habr_query(USER, query)
    else:
        
        display.set_pos(200,4)
        display.set_font(tt32)
        display.set_color(color565(255, 255, 255), HEAD_BGR)

        if(sync_done):
            _, _, _, hour, minute, second, _, _ = time.localtime(time.time() + TIMEZONE_SEC)
            curr_time = "{:02}:{:02}:{:02}".format(hour, minute, second)
        else:
            curr_time = "No time"
            
        display.print(curr_time)
        
        status("Score update after {} seconds".format(last_query + QUERY_SEC - time.time()))
        time.sleep(1)
        continue

    print(res)

   
#    time.sleep(5)
    
    # Print user rating
    # USER KARMA SCORE
    
    USER_OFFSET = 50

    display.set_pos(4, USER_OFFSET+4)
    display.set_font(tt24)
    display.set_color(color565(0, 0, 0), CLR_BG)
    display.print(" User:")
    
    display.set_pos(80, USER_OFFSET)
    display.set_font(tt32)
    display.set_color(color565(100, 150, 180), CLR_BG)
    display.print("@"+USER)

    if(res['KARMA'] and len(res['KARMA'])>1 and res['KARMA'][0] == '-'):
        CLR_KARMA = color565(255, 0, 0)
    else:
        CLR_KARMA = color565(0, 255, 0)

    display.set_pos(4, USER_OFFSET+45)
    display.set_font(tt24)
    display.set_color(color565(0, 0, 0), CLR_BG)
    display.print("Karma:")

    display.set_pos(85, USER_OFFSET+40)
    display.set_font(tt32)
    display.set_color(CLR_KARMA, CLR_BG)
    if(res['KARMA']):
        display.print(res['KARMA'])
    

    display.set_pos(150, USER_OFFSET+45)
    display.set_font(tt24)
    display.set_color(color565(0, 0, 50), CLR_BG)
    display.print("Score:")

    display.set_pos(250, USER_OFFSET+40)
    display.set_font(tt32)
    if(res['SCORE']):
        display.print(res['SCORE'])

    # Print the rating of the latest article
    # VOTES BOOKMARK COMMENTS VIEWS

    ARTICLE_OFFSET = 130

    display.set_pos(20, ARTICLE_OFFSET+4)
    display.set_font(tt24)
    display.set_color(color565(120, 120, 120), CLR_BG)
    display.print("Rating of the latest article:")
    
    if(res['VOTES'] and len(res['VOTES'])>1 and res['VOTES'][0] == '-'):
        CLR_VOTES = color565(255, 0, 0)
    else:
        CLR_VOTES = color565(0, 255, 0)

    display.set_pos(30, ARTICLE_OFFSET+40)
    display.set_font(tt32)
    display.set_color(CLR_VOTES, CLR_BG)
    if(res['VOTES']):
        display.print(res['VOTES'])


    display.set_pos(90, ARTICLE_OFFSET+40)
    display.set_font(tt32)
    display.set_color(color565(0, 0, 0), CLR_BG)
    if(res['VIEWS']):
        display.print(res['VIEWS'])

    display.set_pos(180, ARTICLE_OFFSET+40)
    display.set_font(tt32)
    display.set_color(color565(0, 0, 0), CLR_BG)
    if(res['COMMENTS']):
        display.print(res['COMMENTS'])

    display.set_pos(260, ARTICLE_OFFSET+40)
    display.set_font(tt32)
    display.set_color(color565(0, 0, 0), CLR_BG)
    if(res['BOOKMARK']):
        display.print(res['BOOKMARK'])

    display.set_font(tt14)
    display.set_color(color565(180, 180, 180), CLR_BG)
    display.set_pos(25, ARTICLE_OFFSET+70)
    display.print('Votes')
    display.set_pos(100, ARTICLE_OFFSET+70)
    display.print('Views')
    display.set_pos(160, ARTICLE_OFFSET+70)
    display.print('Comments')
    display.set_pos(240, ARTICLE_OFFSET+70)
    display.print('Bookmarks')


sys.exit()




