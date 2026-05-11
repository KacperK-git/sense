import os
import spidev as SPI
from lib import LCD_1inch47
from PIL import Image, ImageDraw, ImageFont


class Settings(object):
    RESOLUTION = (172, 320)
    DEFAULT_SPI_FREQ = 40000000
    def __init__(self):
        self.RST                  = 27
        self.DC                   = 25
        self.BL                   = 18
        self.bus                  = 0
        self.device               = 0

        self.SPI_FREQ             = 40000000

        self.resolution           = (172, 320)

        self.Font                 = ImageFont.truetype("./Font/OpenSans-Regular.ttf", 24)


def init_and_clear_screen():
    settings = Settings()
    disp = init_screen(settings)
    disp.ShowImage(create_image())
    disp.module_exit()


def init_screen(settings):
    disp = LCD_1inch47.LCD_1inch47(spi=SPI.SpiDev(settings.bus,settings.device),
                                   spi_freq=settings.SPI_FREQ,
                                   rst=settings.RST,
                                   dc=settings.DC,
                                   bl=settings.BL)
    disp.Init()
    disp.clear()
    return disp


def create_image(background="BLACK"):
    return Image.new("RGB", Settings.RESOLUTION, background)


def derive_draw(image):
    draw = ImageDraw.Draw(image)
    draw.rectangle([(0, 0), image.size], fill="BLACK")
    return draw


def prepare_txt(txt, lim=12):
    for i in range(len(txt)):
        temp = txt[i].split(":")
        prefix = temp[0]
        suffix = temp[1]
        num_spaces = lim - len(prefix) - len(suffix)
        new_str = prefix + ' ' * num_spaces + suffix
        txt[i] = new_str
    return txt


def lcd_write(lcd, txt):
    lcd_print_menu(lcd)
    lcd_print_content(lcd, txt)
    lcd.Display.ShowImage(lcd.Image)
    lcd.reset_frame()


def lcd_clear(lcd):
    lcd.Display.ShowImage(lcd.DefaultImage)


def lcd_print_menu(lcd):
    sep = Settings.RESOLUTION[0] // lcd.menu_size
    c_width = 10
    brackets_width = c_width * 3

    for i in range(lcd.menu_size):
        menu = ""
        if i == lcd.current_menu:
            menu += "[X]"
        else:
            menu += "[  ]"
        pos_x = i * sep + sep // 2 - brackets_width // 2
        lcd.Draw.text((pos_x, 5), menu, fill="WHITE", font=lcd.Settings.Font)


def lcd_print_content(lcd, txt):
    cur_y = 60
    for i in range(len(txt)):
        try:
            prefix, suffix = txt[i].split(":")
        except ValueError as e:
            print(f"{txt[i]}\n{e}")

        if lcd.current_menu >= 2 and lcd.vertical_pos == i:
            fill_color = "BLACK"
            highlight_color = "WHITE"
        else:
            fill_color = "WHITE"
            highlight_color = "BLACK"


        # Draw a rectangle for highlight
        lcd.Draw.rectangle([(0, cur_y + 5), (172, cur_y + 30)], fill=highlight_color)

        # Draw the prefix text to the left
        lcd.Draw.text((10, cur_y), prefix, fill=fill_color, font=lcd.Settings.Font)

        # Get the width of the suffix text
        suffix_width = lcd.Draw.textsize(suffix, font=lcd.Settings.Font)[0]

        # Calculate the right-side position of the suffix text
        suffix_pos_x = 172 - 10 - suffix_width

        # Draw the suffix text to the right
        lcd.Draw.text((suffix_pos_x, cur_y), suffix, fill=fill_color, font=lcd.Settings.Font)

        cur_y += 25  # increment y position for next text
    return True


def lcd_length_test(lcd):
    fonts_dir = "./Font/"
    for filename in os.listdir(fonts_dir):
        if filename.endswith(".ttf"):
            font_path = os.path.join(fonts_dir, filename)
            lcd.Settings.Font = ImageFont.truetype(font_path, 24)

            lcd_clear(lcd)
            lcd.Draw.text((10, 120), 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', fill="WHITE", font=lcd.Settings.Font)
            lcd.Draw.text((10, 160), '123456789012345678901234567890', fill="WHITE", font=lcd.Settings.Font)
            lcd.Display.ShowImage(lcd.Image)
            input(f"Now showing {font_path}")
            lcd_clear(lcd)
