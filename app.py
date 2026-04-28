import textwrap
import json
import base64
from flask import Flask, render_template, request, send_file, redirect, url_for, session
from flask_mail import Mail, Message
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
app.secret_key = 'andale_archive_v12_FULL_RESTORE_FIX'

# --- ORIGINAL MAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')
mail = Mail(app)

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

def image_to_ascii(image_file, width=80, density_value=50):
    try:
        img = Image.open(image_file).convert('L')
        aspect_ratio = img.height / img.width
        new_height = int(aspect_ratio * width * 0.5) 
        img = img.resize((width, new_height))
        # Maps 0-100 slider to character density
        if density_value < 33: chars = " .:-' "
        elif density_value < 66: chars = r"WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
        else: chars = r"█▓▒░@#W$8&%*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
        pixels = img.getdata()
        ascii_str = "".join(chars[int((p / 255) * (len(chars) - 1))] for p in pixels)
        return "\n".join(ascii_str[i:i+width] for i in range(0, len(ascii_str), width))
    except: return ""

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST' and 'email_sub' in request.form:
        # Mail subscription logic
        return redirect(url_for('index'))
    return render_template('index.html', gallery=gallery_archive, logo_ascii=LOGO_ASCII)

@app.route('/submit', methods=['POST'])
def submit():
    txt = request.form.get('user_text', '')
    desc = request.form.get('description', 'SIGNAL_LOG')
    # FIX: Explicitly capture 'density_slider' to prevent the crash/disappearing bug
    try:
        density = int(request.form.get('density_slider', 50))
    except (TypeError, ValueError):
        density = 50
    
    img_file = request.files.get('image_file')
    ascii_art = image_to_ascii(img_file, density_value=density) if img_file else ""
    
    entry = {"content": txt, "desc": desc.upper(), "time": datetime.datetime.now().strftime("%H:%M:%S"), "date": datetime.datetime.now().strftime("%Y-%m-%d"), "ascii": ascii_art}
    gallery_archive.insert(0, entry)
    session['last_artifact_ready'] = True
    return redirect(url_for('index'))

@app.route('/download_receipt')
def download_receipt():
    if not gallery_archive: return redirect(url_for('index'))
    inv = request.args.get('invert') == 'true'
    WIDTH, ASCII_H = 1000, 10
    bg, fg = ((0,0,0), (255,255,255)) if inv else ((255,255,255), (0,0,0))
    entry = gallery_archive[0]
    ascii_lines = entry['ascii'].split('\n') if entry['ascii'] else []
    img = Image.new('RGB', (WIDTH, 700 + len(ascii_lines)*ASCII_H), color=bg)
    d = ImageDraw.Draw(img)
    y = 80
    for line in LOGO_ASCII.strip().split('\n'):
        d.text((60, y), line, fill=fg); y += ASCII_H
    y += 60
    for line in ascii_lines:
        d.text((60, y), line, fill=fg); y += ASCII_H
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name="RECEIPT.png")

if __name__ == '__main__':
    app.run(debug=True)