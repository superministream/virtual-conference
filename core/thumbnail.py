import io
import qrcode
from PIL import Image, ImageDraw, ImageFont

def compute_text_bounds(text, font):
    ascent, descent = font.getmetrics()
    lines = text.split("\n")
    text_bounds = [0, 0]
    for l in lines:
        box = font.getbbox(l)
        text_bounds[0] = max(text_bounds[0], box[2])
        text_bounds[1] += box[3] + descent
    return text_bounds

# Binary search to fit the biggest text we can in the bounds specified
def fit_text_to_bounds(text, font_file, width, height, max_font_size=0):
    max_size = min(height, 128)
    if max_font_size > 0:
        max_size = max_font_size
    min_size = 16
    font = None
    bounds = None
    while max_size > min_size:
        size = int((max_size + min_size) / 2)
        font = ImageFont.truetype(font_file, size=size)
        bounds = compute_text_bounds(text, font)
        if bounds[0] > width or bounds[1] > height:
            max_size = size - 1
        else:
            min_size = size + 1
    return font

# Renders the thumbnail out to an io.BytesIO object
# NOTE: You'll probably want to adjust the text placement to better
# fit your own session title layout
def render_thumbnail(background_file, fonts, title, chair, schedule, qr_string=None):
    # If we don't have a space between consecutive newlines they'll be lost and we'll miscompute
    # the text height
    schedule = schedule.replace("\n\n", "\n \n")
    # Assumed 1920x1080, these positions are hard-coded to fit on the background image nicely
    title_font = fit_text_to_bounds(title, fonts["bold"], 1920 - 160, 110)
    chair_font = fit_text_to_bounds(chair, fonts["italic"], 1920 - 160, 72)
    schedule_font = fit_text_to_bounds(schedule, fonts["regular"], 1920 - 200, 640, max_font_size=40)

    background = Image.open(background_file)
    
    if qr_string:
        qr = qrcode.make(qr_string, border=1)
        qr = qr.resize((300, 300), resample=Image.NEAREST)
        background.paste(qr, (1920-300,1080-300, 1920, 1080))

    draw = ImageDraw.Draw(background)
    draw.text((80, 180), title, font=title_font, fill="white")
    draw.text((80, 280), chair, font=chair_font, fill="white")
    draw.text((80, 370), schedule, font=schedule_font, fill="white")

    img_bytes = io.BytesIO()
    background.save(img_bytes, format="png")
    return img_bytes

