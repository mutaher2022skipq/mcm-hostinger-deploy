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
    """Generates a clean, printable Roll Number Slip PDF and returns it as bytes."""
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # 🔰 Header
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 70, "MILITARY COLLEGE MURREE")
    p.setFont("Helvetica-Bold", 13)
    p.drawCentredString(width / 2, height - 90, "ROLL NUMBER SLIP – ENTRANCE TEST 2026")

    # 🏫 Logo
    logo_path = os.path.join(settings.BASE_DIR, "static", "images", "logo.png")
    if os.path.exists(logo_path):
        p.drawImage(logo_path, 70, height - 130, width=60, height=60, preserveAspectRatio=True)

    # 🪪 Candidate Photo
    if application.photo:
        try:
            p.drawImage(application.photo.path, width - 150, height - 230, width=100, height=100)
        except Exception:
            p.setFont("Helvetica-Oblique", 9)
            p.drawString(width - 150, height - 230, "[Photo not available]")

    # 📋 Applicant Details
    p.setFont("Helvetica", 11)
    details = [
        ["Roll Number", application.roll_number or "—"],
        ["Candidate Name", application.name],
        ["Father's Name", application.father_name],
        ["Category", dict(application.CATEGORY_CHOICES).get(application.category, application.category or "—")],
        ["Test Center", dict(application.TEST_CENTERS).get(application.test_center, application.test_center or "—")],
        ["Date of Birth", application.dob.strftime("%d-%b-%Y") if application.dob else "—"],
    ]
    table = Table(details, colWidths=[150, 350])
    table.setStyle(TableStyle([
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONT", (0, 0), (-1, -1), "Helvetica", 11),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
    ]))
    table.wrapOn(p, 80, height - 300)
    table.drawOn(p, 80, height - 380)

    # 🕒 Exam Instructions
    y = height - 420
    p.setFont("Helvetica-Bold", 11)
    p.drawString(80, y, "INSTRUCTIONS:")
    p.setFont("Helvetica", 10)

    # Dynamic instructions based on class
    if application.class_name == 'XI':
        lines = [
            "1. Report at the respective center by 0800 hrs.",
            "2. The written test will start at 0900 hrs and last 4 hours (till 1300 hrs).",
            "3. Subjects: English, Mathematics, Physics, Chemistry.",
            "4. Bring this printed Roll Number Slip and writing material. Calculator is also allowed.",
            "5. Bring writing material; exam booklet will be provided.",
            "6. Mobile phones are strictly prohibited.",
            "7. Parents/Guardians must bring CNIC.",
        ]
    else:
        # Default for Class VIII
        lines = [
            "1. Report at the respective center by 0800 hrs.",
            "2. The written test will start at 0900 hrs and last 3 hours (till 1200 hrs).",
            "3. Subjects: English, Mathematics, Urdu, Islamiat.",
            "4. Bring this printed Roll Number Slip and your CNIC/Form-B.",
            "5. Bring writing material; exam booklet will be provided.",
            "6. Mobile phones are strictly prohibited.",
            "7. Parents/Guardians must bring CNIC.",
        ]

    for line in lines:
        y -= 18
        p.drawString(100, y, line)

    y -= 30
    p.setFont("Helvetica-Oblique", 9)
    p.drawString(80, y, "Admission Office – Military College Murree")
    p.line(80, y - 25, width - 80, y - 25)

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