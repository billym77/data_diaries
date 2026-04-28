import textwrap
import json
import base64
from flask import Flask, render_template, request, send_file, redirect, url_for, session
from flask_mail import Mail, Message
from PIL import Image, ImageDraw, ImageFont
import datetime
import io
import os
import threading
import random

# PDF Generation imports
from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors as rl_colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)
app.secret_key = 'andale_archive_v10_zine_master'

# --- MAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

mail = Mail(app)

# Global Storage
gallery_archive = []
subscribers = []

LOGO_ASCII = """
######   ######  ########  ######            ########  ####   ######   #######   ####  ########  ######
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##      ##    ##
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##      ##    ##
##    ## ########    ##    ########  ####### ##     ##  ##   ######## #########  ##   ######    ######
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##            ##
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##      ##    ##
######   ##    ##    ##    ##    ##          ########  ####  ##    ## ##     ## ####  ########  ######
"""

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"DEBUG: Background broadcast failed: {e}")

def image_to_ascii(image_file, width=100, density_level="medium"):
    try:
        img = Image.open(image_file).convert('L')
        aspect_ratio = img.height / img.width
        new_height = int(aspect_ratio * width * 0.55)
        img = img.resize((width, new_height))
        if density_level == "light":
            chars = " .:-' "
        elif density_level == "heavy":
            chars = "█▓▒░@#W$8&%*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
        else:
            chars = "WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
        pixels = img.getdata()
        ascii_str = ""
        for i, pixel in enumerate(pixels):
            if i % width == 0 and i != 0:
                ascii_str += "\n"
            index = int((pixel / 255) * (len(chars) - 1))
            ascii_str += chars[index]
        return ascii_str
    except:
        return "[SIGNAL_LOST]"

def get_font(size):
    paths = ["Andale Mono.ttf", "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def create_receipt_image(text, ascii_art="", redaction_level=0):
    WIDTH = 800
    CHAR_W, CHAR_H, ASCII_CHAR_H = 9, 18, 8
    font_main, font_small, font_ascii = get_font(14), get_font(9), get_font(7)
    wrapper = textwrap.TextWrapper(width=60)
    content_lines = wrapper.wrap(text.upper()) if text else []
    ascii_lines = ascii_art.split('\n') if ascii_art else []
    logo_h = len(LOGO_ASCII.strip().split('\n')) * ASCII_CHAR_H + 20
    ascii_h = len(ascii_lines) * ASCII_CHAR_H + 40 if ascii_art else 0
    text_h = len(content_lines) * CHAR_H + 20
    total_h = 80 + logo_h + 60 + ascii_h + text_h + 120
    img = Image.new('RGB', (WIDTH, total_h), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    y = 40
    for line in LOGO_ASCII.strip().split('\n'):
        d.text((40, y), line, fill=(0, 0, 0), font=font_ascii); y += ASCII_CHAR_H
    y += 20
    d.text((40, y), f"DATA_DIARY_ARTIFACT // TS: {ts}", fill=(0, 0, 0), font=font_small); y += 16
    d.text((40, y), "-" * 72, fill=(0, 0, 0), font=font_small); y += 30
    if ascii_art:
        for line in ascii_lines:
            d.text((40, y), line, fill=(0, 0, 0), font=font_ascii); y += ASCII_CHAR_H
        y += 30
    text_start_y = y
    for line in content_lines:
        d.text((40, y), line, fill=(0, 0, 0), font=font_main); y += CHAR_H
    y += 40
    d.text((40, y), "-" * 72, fill=(0, 0, 0), font=font_small); y += 14
    d.text((40, y), "DATA-DIAIRES.XYZ // ARCHIVE STATUS: COMMITTED", fill=(180, 180, 180), font=font_small)
    if redaction_level > 0:
        rng = random.Random(42)
        y_scan = text_start_y
        for line in content_lines:
            words = line.split()
            for wi, word in enumerate(words):
                if rng.random() < [0, 0.3, 0.55, 0.75][redaction_level]:
                    prefix = ' '.join(words[:wi])
                    x_off = 40 + int(len(prefix) * CHAR_W * 0.85)
                    w_px = int(len(word) * CHAR_W * 0.85) + 4
                    d.rectangle((x_off, y_scan, x_off + w_px, y_scan + CHAR_H - 2), fill=(0, 0, 0))
            y_scan += CHAR_H
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return buf

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        email_sub = request.form.get('email_sub')
        if email_sub:
            if email_sub not in subscribers: subscribers.append(email_sub)
            return redirect(url_for('index'))
        txt = request.form.get('user_text', '')
        desc = request.form.get('description', 'SIGNAL_LOG')
        img_file = request.files.get('image_file')
        ascii_art = image_to_ascii(img_file) if img_file and img_file.filename else ""
        entry = {"content": txt, "desc": desc.upper(), "time": datetime.datetime.now().strftime("%H:%M:%S"), "date": datetime.datetime.now().strftime("%Y-%m-%d"), "ascii": ascii_art}
        gallery_archive.insert(0, entry)
        session['last_entry_index'] = 0
        return redirect(url_for('index'))
    return render_template('index.html', gallery=gallery_archive, logo_ascii=LOGO_ASCII)

@app.route('/zine/<mode>')
def zine(mode):
    if not gallery_archive: return redirect(url_for('index'))
    W, H = A5
    buf = io.BytesIO()
    cv = rl_canvas.Canvas(buf, pagesize=A5)
    PAD = 14 * mm
    for ei, entry in enumerate(gallery_archive):
        redact = 3 if mode == 'redacted' else 0
        cv.setFont('Courier-Bold', 8)
        cv.drawString(PAD, H - 10*mm, f"DATA_DIARIES // ARTIFACT_{ei+1:03d}")
        cv.drawRightString(W - PAD, H - 10*mm, f"TS: {entry['date']}")
        y = H - 25*mm
        cv.setFont('Courier', 10)
        lines = textwrap.wrap(entry['content'].upper(), width=40)
        for line in lines:
            if redact == 3:
                tw = cv.stringWidth(line, 'Courier', 10)
                cv.rect(PAD, y-2, tw, 10, fill=1)
            else:
                cv.drawString(PAD, y, line)
            y -= 15
        cv.showPage()
    cv.save(); buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f'DATA_DIARIES_ZINE_{mode.upper()}.pdf')

@app.route('/download_artifact')
def download_artifact():
    idx = session.get('last_entry_index', 0)
    if gallery_archive and idx < len(gallery_archive):
        entry = gallery_archive[idx]
        buf = create_receipt_image(entry['content'], entry['ascii'])
        return send_file(buf, mimetype='image/png', as_attachment=True, download_name=f"{entry['desc']}.png")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)