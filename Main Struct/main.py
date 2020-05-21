#! /usr/bin/env python3

import pygame as pg
from time import time, sleep
import cv2 as cv
import os
from datetime import datetime

from constant import *
from color import *

try:
    from modbus import plc
    print('Modbus module import success.')
except:
    print('Modbus module import failed.')
    exit()

try:
    from picamera import PiCamera
    from picamera.array import PiRGBArray
    print('Camera module import success.')
except:
    print('Camera module import failed.')

### initialize keyboard ###
try:
    import kb
    kb.init()
    print('Keyboard initialize success.')

except:
    pass


##### values can be controled #####
torch_speed_value_mm_per_min = 200
solder_speed_value_v = 2
## values will read from PLC ##
gun_height_value = 0
v_value, a_value = 0, 0

######## iniaialize interface(pygame) ########
pg.init()
pg.font.init()

font = pg.font.SysFont('Noto Sans CJK', 40)
font_small = pg.font.SysFont('Noto Sans CJK', 24)

W, H = 370, 272
WIN = pg.display.set_mode((W, H))
# WIN = pg.display.set_mode((W, H), pg.FULLSCREEN)
### initialize modbus connect ###
plc_main = plc()
if plc_main.is_connected:
    print('PLC connected.')
else:
    print('PLC connection error, please check PLC and ethernet cable.')

### initialize camera, including parameters ###
try:
    camera_resolution = (640, 480)
    camera = PiCamera()
    camera.resolution = camera_resolution
    camera.brightness = 25
    rawCapture = PiRGBArray(camera, size=camera_resolution)
except:
    print('Camera cannot be used.')
####### functions #######


def draw_title(text: str, color=WHITE, y=120):
    text = font.render(text, True, color)

    width = text.get_width()
    x = (W - width)//2
    WIN.blit(text, (x, y))


def draw_text(text: str, position: int, line: bool = 0, color=YELLOW):
    if type(text) != str:
        return

    if not line:
        text = font.render(text, True, color)
        y = 210
    else:
        text = font_small.render(text, True, color)
        y = 240

    width = text.get_width()
    x = W//6 * (position*2 - 1) - width//2
    WIN.blit(text, (x, y))


def draw_automode_window():
    WIN.fill(BLACK)
    draw_title('AUTO MODE')


def draw_menual_window():

    WIN.fill(BLACK)
    draw_title('MANUAL MODE')
    if torch_speed_value_mm_per_min > 2000:
        draw_text(str(torch_speed_value_mm_per_min), 1, color=RED)
    else:
        draw_text(str(torch_speed_value_mm_per_min), 1)
    draw_text('mm/min', 1, 1)
    draw_text(str(solder_speed_value_v), 2)
    draw_text('V', 2, 1)
    draw_text(f'{str(v_value)}/{str(a_value)}', 3)
    draw_text('V/A', 3, 1)


def draw_error_window(message):
    WIN.fill(RED)
    draw_title(message, WHITE)


def draw_message_window(message: str, msg_color: list = WHITE, bgcolor: list = RED):
    WIN.fill(bgcolor)
    draw_title(message, msg_color)


def draw_setting_value_window(id: int, value: str):
    font_color = WHITE
    WIN.fill(BLACK)
    if id == TORCH_SPEED_VALUE:
        if value != '' and int(value) > 2000:
            font_color = RED
        draw_title('SETTING TORCH', y=40)
    elif id == SOLDER_SPEED_VALUE:
        draw_title('SETTING SOLDER', y=40)
    draw_title('SPEED VALUE', y=90)
    val = font.render(value, True, font_color)
    width = val.get_width()
    x = W//2 - width//2
    WIN.blit(val, (x, 180))


def set_val(id: int):
    kb_locked = False
    temp = ''
    while True:
        key = kb.scan()

        if plc_main.setting_value_end():
            if temp != '':
                if id == TORCH_SPEED_VALUE:
                    temp = int(temp)
                    global torch_speed_value_mm_per_min
                    torch_speed_value_mm_per_min = temp
                    plc_main.write_value(id, temp)
                elif id == SOLDER_SPEED_VALUE:
                    temp = float(temp)
                    global solder_speed_value_v
                    solder_speed_value_v = temp
                    plc_main.write_value(id, temp)
            else:
                pass
            return

        if key == '#':
            temp = temp[:-1]
        elif key == '*':
            if id == SOLDER_SPEED_VALUE:
                temp += '.'
        elif key != 0:
            if not kb_locked:
                temp += key
                if id == TORCH_SPEED_VALUE:
                    temp = '4000' if int(temp) > 4000 else temp
                elif id == SOLDER_SPEED_VALUE:
                    temp = '10' if float(temp) > 10 else temp
                kb_locked = True

        else:
            kb_locked = False

        draw_setting_value_window(id, temp)
        pg.display.update()

        sleep(0.1)


def close():
    try:
        pg.quit()
        kb.close()
        plc_main.disconnect()
    finally:
        exit()


connect_check_record_time = time()
# main struct
while True:
    # quit scrpit(for keyboard)
    for event in pg.event.get():
        if event.type == pg.QUIT or (event.type == pg.KEYDOWN and (event.key == pg.K_ESCAPE or pg.K_q)):
            close()

    if plc_main.connect():
        mode = plc_main.get_status()
        # 自動模式
        if mode == AUTO_MODE:
            # 影像辨識
            if plc_main.send_start_autorun():
                print('start recording ...')
                time_now = datetime.now()

                camera.start_recording(
                    f'{time_now.year}{time_now.month:02d}{time_now.day:02d}--{time_now.hour:02d}:{time_now.minute}.h264')
                camera.start_preview()
                camera.wait_recording(30)
                camera.stop_recording()
                camera.stop_preview()
                print('recorded success.')
            draw_automode_window()

        # 手動模式
        elif mode == MENUAL_MODE:
            try:
                if plc_main.setting_value():
                    print('Setting Value')
                    if plc_main.is_setting_value(SET_GUN_SPEED):
                        set_val(TORCH_SPEED_VALUE)
                        print(torch_speed_value_mm_per_min)
                    elif plc_main.is_setting_value(SET_SOLDER_SPEED):
                        set_val(SOLDER_SPEED_VALUE)
                        print(solder_speed_value_v)
                    else:
                        pass
            except Exception as e:
                print(e)

            draw_menual_window()

        elif mode == 14234423:  # reset
            draw_message_window('RESETING...', bgcolor=BLACK)

    # 連線錯誤
    else:
        if (time() - connect_check_record_time) // 5:
            connect_check_record_time = time()
            print('PLC connection error, please check PLC and ethernet cable.')

        draw_message_window('Connection Error')

    # PLC送出關機指令
    if plc_main.send_shutdown():
        print('system shutdown...')
        os.system('sudo shutdown now')

    pg.display.update()
    sleep(0.1)


close()