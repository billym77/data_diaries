import textwrap
import io
import os
import datetime
import random
import threading
 
from flask import Flask, render_template, request, send_file, redirect, url_for, session
from flask_mail import Mail, Message
from PIL import Image, ImageDraw, ImageFont
 
from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors as rl_colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
 
app = Flask(__name__)
app.secret_key = 'data_diaires_master_v14'
 
app.config['MAIL_SERVER']         = 'smtp.gmail.com'
app.config['MAIL_PORT']           = 587
app.config['MAIL_USE_TLS']        = True
app.config['MAIL_USERNAME']       = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD']       = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')
mail = Mail(app)
 
gallery_archive = []
subscribers     = []
 
LOGO_ASCII = r"""
######   ######  ########  ######            ########  ####   ######   #######   ####  ########  ######
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##      ##    ##
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##      ##    ##
##    ## ########    ##    ########  ####### ##     ##  ##   ######## #########  ##   ######    ######
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##            ##
##    ## ##    ##    ##    ##    ##          ##     ##  ##   ##    ## ##     ##  ##   ##      ##    ##
######   ##    ##    ##    ##    ##          ########  ####  ##    ## ##     ## ####  ########  ######
"""
 
def get_font(size, bold=False):
    candidates = [
        "Andale Mono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"    if bold else
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()
 
def image_to_ascii(image_file, width=80, density_value=50):
    try:
        img = Image.open(image_file).convert('L')
        aspect_ratio = img.height / img.width
        new_height   = int(aspect_ratio * width * 0.5)
        img          = img.resize((width, new_height))
        if density_value < 33:
            chars = " .:-' "
        elif density_value < 66:
            chars = r"WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
        else:
            chars = r"MWNBA@#$8&%*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
        pixels    = img.getdata()
        ascii_str = "".join(chars[int((p/255)*(len(chars)-1))] for p in pixels)
        return "\n".join(ascii_str[i:i+width] for i in range(0, len(ascii_str), width))
    except Exception:
        return ""
 
def create_receipt_image(entry, invert=False, redact=False, redact_pct=30):
    bg  = (0,0,0)       if invert else (255,255,255)
    fg  = (255,255,255) if invert else (0,0,0)
    dim = (120,120,120) if invert else (180,180,180)
    WIDTH  = 1000
    CHAR_H = 10
    LINE_H = 22
    font_body  = get_font(14)
    font_small = get_font(10)
    font_ascii = get_font(8)
    txt           = entry.get('content', '')
    ascii_art     = entry.get('ascii', '')
    desc          = entry.get('desc', 'UNKNOWN')
    ts            = f"{entry.get('date','')} {entry.get('time','')}"
    wrapper       = textwrap.TextWrapper(width=80)
    content_lines = wrapper.wrap(txt.upper()) if txt else []
    ascii_lines   = ascii_art.split('\n') if ascii_art else []
    logo_lines    = LOGO_ASCII.strip().split('\n')
    total_h = (80 + len(logo_lines)*CHAR_H + 30 + 60
               + len(ascii_lines)*CHAR_H + 30
               + len(content_lines)*LINE_H + 40 + 60)
    img = Image.new('RGB', (WIDTH, max(total_h, 400)), color=bg)
    d   = ImageDraw.Draw(img)
    y = 60
    for line in logo_lines:
        d.text((60, y), line, fill=fg, font=font_ascii)
        y += CHAR_H
    y += 20
    d.line([(60,y),(WIDTH-60,y)], fill=fg, width=1); y += 12
    d.text((60,y), f"DATA_DIARY_ARTIFACT // TS: {ts} // ID: {desc}", fill=dim, font=font_small)
    y += 20
    d.line([(60,y),(WIDTH-60,y)], fill=dim, width=1); y += 20
    if ascii_lines:
        for line in ascii_lines:
            d.text((60,y), line, fill=fg, font=font_ascii)
            y += CHAR_H
        y += 20
    rng = random.Random(hash(txt))
    text_start_y = y
    for line in content_lines:
        words = line.split()
        x_cur = 60
        for word in words:
            w_px = len(word)*8+6
            if redact and rng.random() < (redact_pct/100):
                d.rectangle([x_cur-2, y-2, x_cur+w_px, y+LINE_H-4], fill=fg)
            else:
                d.text((x_cur,y), word, fill=fg, font=font_body)
            x_cur += w_px+6
        y += LINE_H
    y += 20
    if redact:
        stamps = ["// CLASSIFIED", f"REF: DD-{entry.get('date','').replace('-','')}", "ARCHIVE STATUS: WITHHELD", "[REDACTED]"]
        sy = text_start_y
        for stamp in stamps:
            sx = rng.randint(60,400)
            d.text((sx,sy), stamp, fill=dim, font=font_small)
            sy += 18
    d.line([(60,y),(WIDTH-60,y)], fill=dim, width=1); y += 12
    d.text((60,y), "DATA-DIAIRES.XYZ  //  ARCHIVE STATUS: COMMITTED", fill=dim, font=font_small)
    if redact:
        y += 14
        d.text((60,y), "INSPIRED BY METAHAVEN — BLACK TRANSPARENCY (2015)", fill=dim, font=font_small)
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return buf
 
def ascii_to_image_bytes(ascii_art):
    if not ascii_art: return None
    lines  = ascii_art.split('\n')
    font   = get_font(8)
    W      = max(max(len(l) for l in lines)*6+20, 100)
    H      = max(len(lines)*10+20, 50)
    img    = Image.new('RGB', (W,H), (255,255,255))
    d      = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((10, 10+i*10), line, fill=(0,0,0), font=font)
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()
 
def send_async_email(app_ctx, msg):
    with app_ctx.app_context():
        try:
            mail.send(msg)
            print("EMAIL: broadcast ok")
        except Exception as e:
            print(f"EMAIL: broadcast failed — {e}")
 
@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        email_sub = request.form.get('email_sub','').strip()
        if email_sub and email_sub not in subscribers:
            subscribers.append(email_sub)
    return render_template('index.html', gallery=gallery_archive, logo_ascii=LOGO_ASCII)
 
@app.route('/submit', methods=['POST'])
def submit():
    txt  = request.form.get('user_text','')
    desc = request.form.get('description','SIGNAL_LOG').upper()
    try:
        density = int(request.form.get('density_slider', 50))
    except (TypeError, ValueError):
        density = 50
    img_file  = request.files.get('image_file')
    ascii_art = image_to_ascii(img_file, density_value=density) if img_file and img_file.filename else ""
    entry = {"content":txt, "desc":desc,
             "time":datetime.datetime.now().strftime("%H:%M:%S"),
             "date":datetime.datetime.now().strftime("%Y-%m-%d"),
             "ascii":ascii_art}
    gallery_archive.insert(0, entry)
    session['has_artifact'] = True
    if subscribers:
        msg = Message(subject=f"SIGNAL_RECEPTION: {desc}", recipients=list(subscribers))
        msg.body = (f"DATA_DIAIRES // NEW ARTIFACT\n{'─'*50}\n"
                    f"ID:   {desc}\nDATE: {entry['date']} {entry['time']}\n{'─'*50}\n\n"
                    f"{txt.upper()}\n\nASCII ART: see attached image\nDATA-DIAIRES.XYZ\n")
        msg.html = f"""<div style="font-family:'Courier New',monospace;max-width:600px;
            margin:0 auto;background:#fff;color:#000;padding:40px;">
            <p style="font-size:11px;letter-spacing:2px;color:#aaa;">DATA_DIAIRES // SIGNAL_RECEPTION</p>
            <hr style="border:none;border-top:1px solid #eee;">
            <p style="font-size:10px;color:#999;">ID: {desc}<br>{entry['date']} // {entry['time']}</p>
            <hr style="border:none;border-top:1px solid #eee;">
            <p style="font-size:14px;line-height:1.8;letter-spacing:1px;">{txt.upper()}</p>
            <hr style="border:none;border-top:1px solid #eee;">
            <p style="font-size:9px;color:#ccc;">ASCII CONVERSION ATTACHED AS IMAGE<br>DATA-DIAIRES.XYZ</p>
            </div>"""
        if ascii_art:
            img_bytes = ascii_to_image_bytes(ascii_art)
            if img_bytes:
                msg.attach("ascii_artifact.png","image/png",img_bytes)
        thread = threading.Thread(target=send_async_email, args=[app, msg])
        thread.daemon = True
        thread.start()
    return redirect(url_for('index'))
 
@app.route('/delete/<int:entry_id>')
def delete_entry(entry_id):
    if 0 <= entry_id < len(gallery_archive):
        gallery_archive.pop(entry_id)
    return redirect(url_for('index'))
 
@app.route('/download_receipt')
def download_receipt():
    if not gallery_archive: return redirect(url_for('index'))
    invert = request.args.get('invert') == 'true'
    redact = request.args.get('redact') == 'true'
    try:
        redact_pct = int(request.args.get('redact_pct', 30))
    except (TypeError, ValueError):
        redact_pct = 30
    buf   = create_receipt_image(gallery_archive[0], invert, redact, redact_pct)
    fname = f"{gallery_archive[0]['desc']}_RECEIPT.png"
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name=fname)
 
@app.route('/zine')
def zine():
    if not gallery_archive: return redirect(url_for('index'))
    redact = request.args.get('redact','true') == 'true'
    try:
        redact_pct = int(request.args.get('redact_pct', 40))
    except (TypeError, ValueError):
        redact_pct = 40
    invert = request.args.get('invert','false') == 'true'
    try:
        pdfmetrics.registerFont(TTFont('ZMono','/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf'))
        pdfmetrics.registerFont(TTFont('ZMonoBold','/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf'))
        mono_font = 'ZMono'; mono_bold = 'ZMonoBold'
    except Exception:
        mono_font = mono_bold = 'Courier'
    W, H = A5; PAD = 14*mm
    buf  = io.BytesIO()
    cv   = rl_canvas.Canvas(buf, pagesize=A5)
    cv.setTitle('DATA_DIAIRES// BLACK_TRANSPARENCY_ZINE')
    bg_col  = rl_colors.black if invert else rl_colors.white
    fg_col  = rl_colors.white if invert else rl_colors.black
    dim_col = rl_colors.Color(0.6,0.6,0.6)
    for ei, entry in enumerate(gallery_archive):
        rng = random.Random(ei*37+13)
        cv.setFillColor(bg_col); cv.rect(0,0,W,H,fill=1,stroke=0)
        cv.setStrokeColor(fg_col); cv.setLineWidth(0.8)
        cv.line(PAD, H-12*mm, W-PAD, H-12*mm)
        cv.setFillColor(fg_col); cv.setFont(mono_bold, 7)
        cv.drawString(PAD, H-9*mm, 'DATA_DIAIRES// BLACK_TRANSPARENCY_ZINE')
        cv.drawRightString(W-PAD, H-9*mm, f'ENTRY {ei+1:03d} / {len(gallery_archive):03d}')
        y = H-16*mm
        cv.setFont(mono_font, 6.5); cv.setFillColor(dim_col)
        cv.drawString(PAD, y, f"ID: {entry['desc']}   //   {entry['date']} {entry['time']}")
        y -= 4*mm
        cv.setStrokeColor(dim_col); cv.setLineWidth(0.3)
        cv.line(PAD,y,W-PAD,y); y -= 5*mm
        if redact:
            cv.saveState()
            cv.setFont(mono_bold, 18)
            sc = rl_colors.white if invert else rl_colors.black
            cv.setFillColor(rl_colors.Color(sc.red,sc.green,sc.blue,alpha=0.06))
            cv.rotate(rng.uniform(-15,15))
            cv.drawString(PAD+rng.uniform(0,18*mm), y-rng.uniform(8*mm,25*mm),
                          rng.choice(['CLASSIFIED','WITHHELD','REDACTED','ARCHIVE_UNKNOWN']))
            cv.restoreState()
        lines = textwrap.wrap(entry['content'].upper(), width=40)
        cv.setFont(mono_font, 9)
        line_h = 5*mm
        for line in lines:
            if y < 32*mm: break
            words = line.split(); x_cur = PAD
            for word in words:
                ww = cv.stringWidth(word+' ', mono_font, 9)
                if redact and rng.random() < (redact_pct/100):
                    cv.setFillColor(fg_col)
                    cv.rect(x_cur-0.5, y-1.5*mm, ww, 4*mm, fill=1, stroke=0)
                else:
                    cv.setFillColor(fg_col); cv.drawString(x_cur, y, word)
                x_cur += ww
            y -= line_h
        y -= 3*mm
        if entry.get('ascii') and y > 38*mm:
            cv.setFont(mono_font, 4.5); cv.setFillColor(dim_col)
            for al in entry['ascii'].split('\n')[:18]:
                if y < 34*mm: break
                cv.drawString(PAD, y, al[:55]); y -= 3*mm
        cv.setFont(mono_font, 6); cv.setFillColor(dim_col)
        cv.drawString(PAD, 22*mm,
                      f"REDACTION: {'ON' if redact else 'OFF'}  PCT: {redact_pct}%  "
                      f"REF: DD-{entry['date'].replace('-','')}-{ei:04d}")
        cv.setStrokeColor(fg_col); cv.setLineWidth(0.5)
        cv.line(PAD,17*mm,W-PAD,17*mm)
        cv.setFont(mono_font,6); cv.setFillColor(dim_col)
        cv.drawString(PAD,13*mm,'DATA-DIAIRES.XYZ  //  BLACK_TRANSPARENCY PROJECT')
        cv.drawString(PAD, 9*mm,'INSPIRED BY METAHAVEN — BLACK TRANSPARENCY (2015)')
        cv.showPage()
    cv.save(); buf.seek(0)
    return send_file(buf, mimetype='application/pdf',
                     as_attachment=True, download_name='DATA_DIAIRES_ZINE.pdf')
 
if __name__ == '__main__':
    app.run(debug=True)