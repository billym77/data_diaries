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
        
        # Fixed escape sequences with raw strings (r"")
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

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', gallery=gallery_archive, logo_ascii=LOGO_ASCII)

@app.route('/submit', methods=['POST'])
def submit():
    txt = request.form.get('user_text', '')
    desc = request.form.get('description', 'SIGNAL_LOG')
    density = request.form.get('density', 'medium')
    img_file = request.files.get('image_file')
    
    ascii_art = ""
    if img_file and img_file.filename:
        ascii_art = image_to_ascii(img_file, density_level=density)
    
    entry = {
        "content": txt, 
        "desc": desc.upper(), 
        "time": datetime.datetime.now().strftime("%H:%M:%S"), 
        "date": datetime.datetime.now().strftime("%Y-%m-%d"), 
        "ascii": ascii_art
    }
    gallery_archive.insert(0, entry)
    session['last_artifact'] = True # Trigger the Zine button
    return redirect(url_for('index'))

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email_sub = request.form.get('email_sub')
    if email_sub and email_sub not in subscribers:
        subscribers.append(email_sub)
    return redirect(url_for('index'))

@app.route('/delete/<int:index_id>')
def delete(index_id):
    if 0 <= index_id < len(gallery_archive):
        gallery_archive.pop(index_id)
    return redirect(url_for('index'))

@app.route('/generate_zine')
def generate_zine():
    if not gallery_archive: return redirect(url_for('index'))
    W, H = A5
    buf = io.BytesIO()
    cv = rl_canvas.Canvas(buf, pagesize=A5)
    PAD = 14 * mm
    for ei, entry in enumerate(gallery_archive):
        cv.setFont('Courier-Bold', 8)
        cv.drawString(PAD, H - 10*mm, f"DATA_DIARIES // ARTIFACT_{ei+1:03d}")
        cv.drawRightString(W - PAD, H - 10*mm, f"TS: {entry['date']}")
        y = H - 25*mm
        cv.setFont('Courier', 10)
        lines = textwrap.wrap(entry['content'].upper(), width=40)
        for line in lines:
            cv.drawString(PAD, y, line)
            y -= 15
        cv.showPage()
    cv.save(); buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name='DATA_DIARIES_ZINE.pdf')

if __name__ == '__main__':
    app.run(debug=True)