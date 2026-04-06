import textwrap
from flask import Flask, render_template, request, send_file, redirect, url_for, session
from flask_mail import Mail, Message
from PIL import Image, ImageDraw, ImageFont
import datetime
import io
import os

app = Flask(__name__)
app.secret_key = 'andale_archive_v8_final'

# --- MAIL CONFIGURATION (Cloud Ready) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('marshallw358@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('cpsnmkekyduhhrwi')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

mail = Mail(app)

# Persistent Storage (resets on server reboot)
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
        
        if density_level == "light":
            chars = " .:-' " 
        elif density_level == "heavy":
            chars = "█▓▒░@#W$8&%*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. " 
        else:
            chars = "WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. " 
            
        pixels = img.getdata()
        ascii_str = ""
        for i, pixel in enumerate(pixels):
            if i % width == 0 and i != 0: ascii_str += "\n"
            index = int((pixel / 255) * (len(chars) - 1))
            ascii_str += chars[index]
        return ascii_str
    except Exception as e:
        print(f"ASCII ERROR: {e}")
        return "[IMAGE_RECEPTION_ERROR]"

def create_receipt_image(text, ascii_art=""):
    width = 800
    try:
        font_path = "Andale Mono.ttf" 
        if os.path.exists(font_path):
            font_main = ImageFont.truetype(font_path, 16)
            font_ascii = ImageFont.truetype(font_path, 8)
        else:
            font_main = ImageFont.load_default()
            font_ascii = ImageFont.load_default()
    except:
        font_main = ImageFont.load_default()
        font_ascii = ImageFont.load_default()

    wrapper = textwrap.TextWrapper(width=60)
    content_lines = wrapper.wrap(text.upper())
    ascii_lines = ascii_art.split('\n') if ascii_art else []
    
    logo_h = 150
    ascii_h = len(ascii_lines) * 8
    text_h = len(content_lines) * 25
    total_height = logo_h + ascii_h + text_h + 300
    
    img = Image.new('RGB', (width, total_height), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    curr_h = 60
    d.text((50, curr_h), LOGO_ASCII, fill=(0, 0, 0), font=font_ascii)
    curr_h += logo_h
    d.text((50, curr_h), f"DATA_DIARY_ARTIFACT // TS: {ts}\n" + "-"*60, fill=(0, 0, 0), font=font_main)
    curr_h += 80
    
    if ascii_art:
        for line in ascii_lines:
            d.text((50, curr_h), line, fill=(0, 0, 0), font=font_ascii)
            curr_h += 8
        curr_h += 40
    
    for line in content_lines:
        d.text((50, curr_h), line, fill=(0, 0, 0), font=font_main)
        curr_h += 25
        
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return buf

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # 1. SUBSCRIPTION LOGIC
        email_sub = request.form.get('email_sub')
        if email_sub:
            if email_sub not in subscribers:
                subscribers.append(email_sub)
            return redirect(url_for('index'))

        # 2. DATA ENTRY LOGIC
        txt = request.form.get('user_text', '')
        desc = request.form.get('description', 'SIGNAL_LOG')
        img_file = request.files.get('image_file')
        density = request.form.get('density', 'medium')
        
        ascii_art = image_to_ascii(img_file, density_level=density) if img_file else ""
        
        entry = {
            "content": txt, "desc": desc.upper(),
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "ascii": ascii_art
        }
        gallery_archive.insert(0, entry)

        # 3. BROADCAST LOGIC (Non-Blocking Wrap)
        session['last_artifact'] = {"txt": txt, "ascii": ascii_art, "name": desc}

        if subscribers:
            try:
                msg = Message(f"SIGNAL_RECEPTION: {desc.upper()}", recipients=subscribers)
                msg.body = f"NEW ARTIFACT RECEIVED.\n\n{txt.upper()}"
                msg.html = f"<div style='font-family:monospace;'><pre style='font-size:8px; line-height:7px;'>{ascii_art}</pre><hr><p>{txt}</p></div>"
                mail.send(msg)
            except Exception as e: 
                print(f"MAIL ERROR BYPASSED: {e}")

        # Instant Redirect to prevent "Freeze"
        return redirect(url_for('index'))
            
    return render_template('index.html', gallery=gallery_archive, logo_ascii=LOGO_ASCII)

@app.route('/delete/<int:entry_id>')
def delete_entry(entry_id):
    if 0 <= entry_id < len(gallery_archive):
        gallery_archive.pop(entry_id)
    return redirect(url_for('index'))

@app.route('/download_artifact')
def download_artifact():
    data = session.get('last_artifact')
    if data:
        # We don't pop here so the user can re-download if needed
        return send_file(create_receipt_image(data['txt'], data['ascii']), 
                         mimetype='image/png', as_attachment=True, 
                         download_name=f"{data['name']}.png")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)