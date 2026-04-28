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

from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors as rl_colors
from reportlab.lib.units import mm

app = Flask(__name__)
app.secret_key = 'andale_archive_v10_zine_master'

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

def image_to_ascii(image_file, width=100, density_level="medium"):
    try:
        img = Image.open(image_file).convert('L')
        aspect_ratio = img.height / img.width
        new_height = int(aspect_ratio * width * 0.55)
        img = img.resize((width, new_height))
        
        # Use Raw Strings r"" to fix Render SyntaxWarnings
        if density_level == "light":
            chars = " .:-' "
        elif density_level == "heavy":
            chars = r"█▓▒░@#W$8&%*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
        else:
            chars = r"WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
            
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

# --- RE-ADDED INDIVIDUAL RECEIPT LOGIC ---
def get_font(size):
    # Fallback logic for Render's Linux environment
    paths = ["/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"]
    for p in paths:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def create_receipt_image(text, ascii_art=""):
    WIDTH = 800
    CHAR_H, ASCII_CHAR_H = 18, 8
    font_main, font_small, font_ascii = get_font(14), get_font(9), get_font(7)
    wrapper = textwrap.TextWrapper(width=60)
    content_lines = wrapper.wrap(text.upper()) if text else []
    ascii_lines = ascii_art.split('\n') if ascii_art else []
    
    total_h = 400 + (len(ascii_lines) * ASCII_CHAR_H) + (len(content_lines) * CHAR_H)
    img = Image.new('RGB', (WIDTH, total_h), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    y = 40
    for line in LOGO_ASCII.strip().split('\n'):
        d.text((40, y), line, fill=(0, 0, 0), font=font_ascii); y += ASCII_CHAR_H
    y += 40
    if ascii_art:
        for line in ascii_lines:
            d.text((40, y), line, fill=(0, 0, 0), font=font_ascii); y += ASCII_CHAR_H
        y += 40
    for line in content_lines:
        d.text((40, y), line, fill=(0, 0, 0), font=font_main); y += CHAR_H
    
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return buf

@app.route('/')
def index():
    return render_template('index.html', gallery=gallery_archive, logo_ascii=LOGO_ASCII)

@app.route('/submit', methods=['POST'])
def submit():
    txt = request.form.get('user_text', '')
    desc = request.form.get('description', 'SIGNAL_LOG')
    density = request.form.get('density', 'medium')
    img_file = request.files.get('image_file')
    ascii_art = image_to_ascii(img_file, density_level=density) if img_file else ""
    
    entry = {"content": txt, "desc": desc.upper(), "time": datetime.datetime.now().strftime("%H:%M:%S"), "date": datetime.datetime.now().strftime("%Y-%m-%d"), "ascii": ascii_art}
    gallery_archive.insert(0, entry)
    session['last_artifact_ready'] = True
    return redirect(url_for('index'))

@app.route('/download_receipt')
def download_receipt():
    if not gallery_archive: return redirect(url_for('index'))
    entry = gallery_archive[0]
    buf = create_receipt_image(entry['content'], entry['ascii'])
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name=f"RECEIPT_{entry['desc']}.png")

@app.route('/generate_zine')
def generate_zine():
    mode = request.args.get('mode', 'full')
    level = float(request.args.get('level', 50)) / 100.0
    W, H = A5
    buf = io.BytesIO()
    cv = rl_canvas.Canvas(buf, pagesize=A5)
    PAD = 14 * mm
    for ei, entry in enumerate(gallery_archive):
        cv.setFont('Courier-Bold', 8)
        cv.drawString(PAD, H-10*mm, f"DATA_DIARIES // {entry['desc']}")
        y = H - 30*mm
        cv.setFont('Courier', 10)
        lines = textwrap.wrap(entry['content'].upper(), width=40)
        for line in lines:
            if mode == 'redacted':
                words = line.split()
                cur_x = PAD
                for w in words:
                    w_w = cv.stringWidth(w + " ", 'Courier', 10)
                    if random.random() < level:
                        cv.rect(cur_x, y-2, w_w-1, 10, fill=1)
                    else:
                        cv.drawString(cur_x, y, w)
                    cur_x += w_w
            else:
                cv.drawString(PAD, y, line)
            y -= 15
        cv.showPage()
    cv.save(); buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f"ZINE_{mode.upper()}.pdf")

@app.route('/delete/<int:id>')
def delete(id):
    if 0 <= id < len(gallery_archive): gallery_archive.pop(id)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)