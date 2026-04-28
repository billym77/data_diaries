import textwrap
import json
import base64
from flask import Flask, render_template, request, send_file, redirect, url_for, session
from PIL import Image, ImageDraw, ImageFont
import datetime
import io
import os
import random

# PDF Generation imports
from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors as rl_colors
from reportlab.lib.units import mm

app = Flask(__name__)
app.secret_key = 'andale_archive_v12_stable_master'

gallery_archive = []

LOGO_ASCII = r"""
######   ######  ########  ######            ########  ####   ######   #######   ####  ########  ######
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##      ##    ##
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##      ##    ##
##    ## ########    ##    ########  ####### ##     ##  ##   ######## #########  ##   ######    ######
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##            ##
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##      ##    ##
######   ##    ##    ##    ##    ##          ########  ####  ##    ## ##     ## ####  ########  ######
"""

def image_to_ascii(image_file, width=80, density_level="medium"):
    try:
        img = Image.open(image_file).convert('L')
        aspect_ratio = img.height / img.width
        # Adjusted for better scaling on receipts
        new_height = int(aspect_ratio * width * 0.5) 
        img = img.resize((width, new_height))
        
        chars = r"WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
        if density_level == "light": chars = " .:-' "
        elif density_level == "heavy": chars = r"█▓▒░@#W$8&%*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
            
        pixels = img.getdata()
        ascii_str = "".join(chars[int((p / 255) * (len(chars) - 1))] for p in pixels)
        return "\n".join(ascii_str[i:i+width] for i in range(0, len(ascii_str), width))
    except: return ""

def create_receipt_image(entry, inverted=False):
    # FIXED: Wider canvas and better line height to prevent distortion
    WIDTH = 1000 
    ASCII_CHAR_H = 10
    bg = (0, 0, 0) if inverted else (255, 255, 255)
    fg = (255, 255, 255) if inverted else (0, 0, 0)
    
    ascii_lines = entry['ascii'].split('\n') if entry['ascii'] else []
    total_h = 700 + (len(ascii_lines) * ASCII_CHAR_H)
    img = Image.new('RGB', (WIDTH, total_h), color=bg)
    d = ImageDraw.Draw(img)
    y = 80
    
    # Logo and Content
    for line in LOGO_ASCII.strip().split('\n'):
        d.text((60, y), line, fill=fg); y += ASCII_CHAR_H
    y += 60
    
    if entry['ascii']:
        for line in ascii_lines:
            # Added slight x-offset to center art better
            d.text((60, y), line, fill=fg); y += ASCII_CHAR_H
    
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return buf

@app.route('/', methods=['GET'])
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
    inv = request.args.get('invert') == 'true'
    buf = create_receipt_image(gallery_archive[0], inverted=inv)
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name="RECEIPT.png")

@app.route('/generate_zine')
def generate_zine():
    if not gallery_archive: return redirect(url_for('index'))
    mode = request.args.get('mode', 'full')
    level = float(request.args.get('level', 50)) / 100.0
    inverted = request.args.get('invert') == 'true'
    
    buf = io.BytesIO()
    cv = rl_canvas.Canvas(buf, pagesize=A5)
    bg_c = rl_colors.black if inverted else rl_colors.white
    fg_c = rl_colors.white if inverted else rl_colors.black
    
    for entry in gallery_archive:
        cv.setFillColor(bg_c)
        cv.rect(0, 0, 148*mm, 210*mm, fill=1)
        cv.setFillColor(fg_c)
        # FIXED: Removed bold Courier to match receipt aesthetic
        cv.setFont('Courier', 10) 
        cv.drawString(15*mm, 190*mm, f"ID: {entry['desc']}")
        y = 175*mm
        for line in textwrap.wrap(entry['content'].upper(), width=35):
            if mode == 'redacted' and random.random() < level:
                cv.rect(15*mm, y-2, cv.stringWidth(line, 'Courier', 10), 10, fill=1)
            else:
                cv.drawString(15*mm, y, line)
            y -= 15
        cv.showPage()
    cv.save(); buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name="DATA_ZINE.pdf")

@app.route('/delete/<int:idx>')
def delete(idx):
    if 0 <= idx < len(gallery_archive): gallery_archive.pop(idx)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)