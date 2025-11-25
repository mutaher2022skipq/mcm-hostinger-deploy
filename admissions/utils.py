from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from io import BytesIO
import os
from django.conf import settings
from datetime import date
from django.core.exceptions import ObjectDoesNotExist
from .models import FeeConfig, FeeCategoryConfig


def generate_roll_number_pdf(application):
    """Generates a professional, beautifully styled Roll Number Slip PDF with MCM branding."""
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # 🎨 MCM Brand Colors
    MCM_GREEN = colors.HexColor("#005430")  # Dark Green
    MCM_GOLD = colors.HexColor("#DAA520")   # Gold
    LIGHT_GRAY = colors.HexColor("#F9F9F9") # Light Gray
    DARK_TEXT = colors.HexColor("#212121")  # Dark Gray/Black
    
    # ═══════════════════════════════════════════════════════
    # 🎨 PROFESSIONAL HEADER BAND (Green Background)
    # ═══════════════════════════════════════════════════════
    p.setFillColor(MCM_GREEN)
    p.rect(40, height - 110, width - 80, 75, fill=1, stroke=0)
    
    # Header Text (White on Green)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 20)
    p.drawCentredString(width / 2, height - 60, "MILITARY COLLEGE MURREE")
    
    # Subtitle (Gold)
    p.setFillColor(MCM_GOLD)
    p.setFont("Helvetica-Bold", 13)
    p.drawCentredString(width / 2, height - 85, "ROLL NUMBER SLIP – ENTRANCE TEST 2026")
    
    # Reset color
    p.setFillColor(DARK_TEXT)
    
    # ═══════════════════════════════════════════════════════
    # 🏫 LOGO (Circular Badge with Gold Border)
    # ═══════════════════════════════════════════════════════
    logo_path = os.path.join(settings.BASE_DIR, "static", "images", "logo.png")
    if os.path.exists(logo_path):
        # Gold circle background
        p.setFillColor(MCM_GOLD)
        p.circle(85, height - 75, 35, fill=1, stroke=0)
        # Logo image
        p.drawImage(logo_path, 55, height - 105, width=60, height=60, preserveAspectRatio=True, mask='auto')
    
    # ═══════════════════════════════════════════════════════
    # 🎫 ROLL NUMBER HIGHLIGHT BOX (Gold Background)
    # ═══════════════════════════════════════════════════════
    roll_y = height - 160
    p.setFillColor(MCM_GOLD)
    p.roundRect(60, roll_y - 35, 220, 45, 8, fill=1, stroke=0)
    
    # Roll Number Text (Large, Bold, White)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 18)
    p.drawString(75, roll_y - 15, "Roll Number:")
    p.setFont("Helvetica-Bold", 22)
    p.drawString(75, roll_y - 32, application.roll_number or "—")
    
    # Reset color
    p.setFillColor(DARK_TEXT)
    
    # ═══════════════════════════════════════════════════════
    # 🪪 CANDIDATE PHOTO (Framed with Green Border)
    # ═══════════════════════════════════════════════════════
    photo_x = width - 165
    photo_y = height - 225
    
    if application.photo:
        try:
            # Green border frame
            p.setStrokeColor(MCM_GREEN)
            p.setLineWidth(3)
            p.rect(photo_x - 3, photo_y - 3, 116, 116, fill=0, stroke=1)
            # Photo
            p.drawImage(application.photo.path, photo_x, photo_y, width=110, height=110, preserveAspectRatio=True, mask='auto')
        except Exception:
            p.setFont("Helvetica-Oblique", 9)
            p.setFillColor(colors.gray)
            p.drawString(photo_x + 10, photo_y + 50, "[Photo not available]")
    
    # ═══════════════════════════════════════════════════════
    # 📋 APPLICANT DETAILS TABLE (Professional Styling)
    # ═══════════════════════════════════════════════════════
    table_y = height - 270
    
    details = [
        ["Candidate Name", application.name],
        ["Father's Name", application.father_name],
        ["Category", dict(application.CATEGORY_CHOICES).get(application.category, application.category or "—")],
        ["Test Center", dict(application.TEST_CENTERS).get(application.test_center, application.test_center or "—")],
        ["Date of Birth", application.dob.strftime("%d-%b-%Y") if application.dob else "—"],
    ]
    
    table = Table(details, colWidths=[140, 360])
    table.setStyle(TableStyle([
        # Header styling (labels)
        ("BACKGROUND", (0, 0), (0, -1), MCM_GREEN),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 11),
        
        # Value cells - alternating colors
        ("BACKGROUND", (1, 0), (1, 0), LIGHT_GRAY),
        ("BACKGROUND", (1, 2), (1, 2), LIGHT_GRAY),
        ("BACKGROUND", (1, 4), (1, 4), LIGHT_GRAY),
        
        # All text styling
        ("TEXTCOLOR", (1, 0), (1, -1), DARK_TEXT),
        ("FONT", (1, 0), (1, -1), "Helvetica", 11),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        
        # Borders
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 2, MCM_GREEN),
        
        # Padding
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    
    table.wrapOn(p, 60, table_y)
    table.drawOn(p, 60, table_y - 120)
    
    # ═══════════════════════════════════════════════════════
    # ⚠ INSTRUCTIONS BOX (Green Header, White Background)
    # ═══════════════════════════════════════════════════════
    instr_y = table_y - 160
    
    # Header box
    p.setFillColor(MCM_GREEN)
    p.rect(60, instr_y, width - 120, 30, fill=1, stroke=0)
    
    # Header text
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 13)
    p.drawString(75, instr_y + 10, "⚠ IMPORTANT INSTRUCTIONS")
    
    # Instructions background
    p.setFillColor(colors.white)
    p.setStrokeColor(MCM_GREEN)
    p.setLineWidth(2)
    p.rect(60, instr_y - 150, width - 120, 150, fill=1, stroke=1)
    
    # Instructions text
    p.setFillColor(DARK_TEXT)
    p.setFont("Helvetica", 10)
    
    # Dynamic instructions based on class
    if application.class_name == 'XI':
        lines = [
            "1. ✓ Report at the respective center by 0800 hrs.",
            "2. 📅 The written test will start at 0900 hrs and last 4 hours (till 1300 hrs).",
            "3. ✏ Subjects: English, Mathematics, Physics, Chemistry.",
            "4. 📋 Bring this printed Roll Number Slip and writing material. Calculator is also allowed.",
            "5. 📝 Bring writing material; exam booklet will be provided.",
            "6. ⛔ Mobile phones are strictly prohibited.",
            "7. 👨‍👩‍👦 Parents/Guardians must bring CNIC.",
        ]
    else:
        # Default for Class VIII
        lines = [
            "1. ✓ Report at the respective center by 0800 hrs.",
            "2. 📅 The written test will start at 0900 hrs and last 3 hours (till 1200 hrs).",
            "3. ✏ Subjects: English, Mathematics, Urdu, Islamiat.",
            "4. 📋 Bring this printed Roll Number Slip and your CNIC/Form-B.",
            "5. 📝 Bring writing material; exam booklet will be provided.",
            "6. ⛔ Mobile phones are strictly prohibited.",
            "7. 👨‍👩‍👦 Parents/Guardians must bring CNIC.",
        ]
    
    y = instr_y - 20
    for line in lines:
        p.drawString(75, y, line)
        y -= 18
    
    # ═══════════════════════════════════════════════════════
    # 📧 FOOTER (Gold Line + Contact Info)
    # ═══════════════════════════════════════════════════════
    footer_y = 80
    
    # Gold separator line
    p.setStrokeColor(MCM_GOLD)
    p.setLineWidth(2)
    p.line(60, footer_y + 30, width - 60, footer_y + 30)
    
    # Footer text
    p.setFillColor(MCM_GREEN)
    p.setFont("Helvetica-Oblique", 9)
    p.drawCentredString(width / 2, footer_y + 10, "Admission Office – Military College Murree")
    
    p.setFillColor(colors.gray)
    p.setFont("Helvetica", 8)
    p.drawCentredString(width / 2, footer_y - 5, "📧 admission@mcm.edu.pk  |  📞 +92-51-9272516")
    
    # ═══════════════════════════════════════════════════════
    # 🔲 PAGE BORDER (Double Green Frame)
    # ═══════════════════════════════════════════════════════
    p.setStrokeColor(MCM_GREEN)
    p.setLineWidth(3)
    p.rect(30, 50, width - 60, height - 100, fill=0, stroke=1)
    
    p.showPage()
    p.save()
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data


def get_fee_by_category(category):
    """
    Legacy fallback fee calculation by category.
    Used when FeeConfig is missing or returns None.
    """
    FEE_MAP = {
        'offr_serving': 3000,
        'offr_retired': 3000,
        'jcos_serving': 2000,
        'jcos_retired': 2000,
        'caf': 2000,
        'civilian': 5000,
        'fata': 2000,
        'balochistan': 2000,
        'gilgit': 2000,
        'ajk': 2000,
        'navy_airforce': 3000,
    }
    return FEE_MAP.get(category or 'civilian', 5000)  # Default to civilian fee



#-----------------------
#Fees setup
#----------------------
def get_dynamic_fee_for_application(application, as_of_date=None):
    """
    Returns (amount, tier) where tier is one of: "normal","late"/"double","final"/"triple"
    Returns (None, 'closed') if applications should be stopped (stop_after_final True and after final_deadline).
    """
    as_of_date = as_of_date or date.today()
    try:
        config = FeeConfig.objects.get(class_name=application.class_name)
    except FeeConfig.DoesNotExist:
        return None, "no-config"

    # stop condition
    if config.stop_after_final and as_of_date > config.final_deadline:
        return None, "closed"

    # XI: flat model
    if application.class_name == "XI":
        if as_of_date <= config.normal_deadline:
            return config.base_fee, "normal"
        elif as_of_date <= config.late_deadline:
            return config.double_fee, "double"
        else:
            return config.triple_fee, "triple"

    # VIII: category-based
    try:
        cat = FeeCategoryConfig.objects.get(fee_config=config, category=application.category)
        if as_of_date <= config.normal_deadline:
            return cat.normal_fee, "normal"
        elif as_of_date <= config.late_deadline:
            return cat.late_fee, "late"
        else:
            return cat.final_fee, "final"
    except FeeCategoryConfig.DoesNotExist:
        # fallback to config base fee if category row missing
        if as_of_date <= config.normal_deadline:
            return config.base_fee, "normal"
        elif as_of_date <= config.late_deadline:
            return config.double_fee, "double"
        else:
            return config.triple_fee, "triple"