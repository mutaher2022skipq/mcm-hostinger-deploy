import threading
from django.core.mail import EmailMessage
import os, base64
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import MessageTemplate, Application
from notifications.models import Notification   # adjust import path if different
from .utils import generate_roll_number_pdf
from django.core.files.base import ContentFile
import logging

 # reuse your existing function
import uuid, os

logger = logging.getLogger(__name__)


# Try importing Celery's shared_task decorator
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False


# ✅ Thread-based background runner (fallback)
def run_in_background(func):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()
    return wrapper


# ✅ Conditional decorator (Celery or Thread)
def background_task(func):
    if CELERY_AVAILABLE:
        return shared_task(func)
    else:
        return run_in_background(func)


# ==========================================
# 📤 Task 1: Broadcast Messages (email + in-app)
# ==========================================
@shared_task
def broadcast_message_task(template_id, send_email=True, send_inapp=True, target='all'):
    try:
        template = MessageTemplate.objects.get(id=template_id)
    except MessageTemplate.DoesNotExist:
        return {'error': 'Template not found'}

    apps_qs = Application.objects.select_related('user').all()  # adjust target filtering if needed

    # prepare base64 logo once
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
    logo_data_uri = None
    try:
        with open(logo_path, 'rb') as f:
            logo_data_uri = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
    except Exception:
        logo_data_uri = None

    for app in apps_qs:
        # personalize
        message_body = template.body.format(
            name=app.name,
            father_name=app.father_name,
            roll_number=app.roll_number or "N/A",
            test_center=app.get_test_center_display(),
            category=app.get_category_display(),
            entry=app.entry,
        )

        if send_inapp:
            try:
                Notification.objects.create(user=app.user, title=template.title, message=message_body)
            except Exception:
                # log error if you have logger; skip failing notifications
                pass

        if send_email and getattr(app.user, 'email', None):
            subject = template.subject or template.title
            html_message = render_to_string('emails/broadcast_template.html', {
                'subject': subject,
                'body': message_body,
                'logo_url': logo_data_uri or request_fallback_logo(),  # see helper below
                'name': app.name
            })
            plain_message = strip_tags(html_message)
            try:
                send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [app.user.email],
                          html_message=html_message, fail_silently=True)
            except Exception:
                pass

    return {'success': True}


@shared_task
def bulk_verify_applications_task(app_ids, base_url):
    """
    Celery task to verify multiple applications, generate roll slips,
    and send emails/notifications asynchronously.
    """
    from django.db import transaction

    for app in Application.objects.filter(id__in=app_ids):
        try:
            with transaction.atomic():
                app.payment_status = 'verified'
                app.status = 'verified'

                # Generate roll number + secure token
                if not app.roll_number:
                    app.roll_number = app.generate_roll_number()
                if not app.secure_token:
                    app.secure_token = uuid.uuid4().hex[:12]
                app.save(update_fields=['payment_status', 'status', 'roll_number', 'secure_token'])

                # Generate and save roll slip PDF
                pdf_data = generate_roll_number_pdf(app)
                filename = f"RollSlip_{app.roll_number}.pdf"
                if app.roll_slip:
                    try:
                        app.roll_slip.delete(save=False)
                    except Exception:
                        pass
                app.roll_slip.save(filename, ContentFile(pdf_data), save=False)
                app.save(update_fields=['roll_slip'])

                # Build download link
                download_link = f"{base_url}/admissions/download-roll-slip/{app.secure_token}/"

                # Compose and send email
                try:
                    email_body = (
                        f"Dear {app.name},\n\n"
                        f"Your application has been verified successfully.\n\n"
                        f"Roll Number: {app.roll_number}\n"
                        f"Father’s Name: {app.father_name}\n"
                        f"Test Center: {app.get_test_center_display()}\n\n"
                        "📅 Examination Schedule:\n"
                        "• Report at respective center: 0800 hrs\n"
                        "• Start of written test: 0900 hrs\n"
                        "• Duration: 3 hours (till 1200 hrs)\n\n"
                        "🖊 Subjects: English, Mathematics, Urdu, and Islamiyat.\n\n"
                        "⚠ Important Instructions:\n"
                        "1. Bring your Roll Number Slip and writing material.\n"
                        "2. Entrance Exam booklet will be provided at the center.\n"
                        "3. Missing the test for any reason means no re-examination.\n"
                        "4. Mobile phones are not allowed.\n"
                        "5. Parents/Guardians must bring CNIC.\n\n"
                        f"👉 Download your Roll Number Slip securely here:\n{download_link}\n\n"
                        "Alternatively, log in to your MCM Admission Portal to download it anytime.\n\n"
                        f"For queries contact: {settings.ADMISSION_CONTACT_EMAIL} | Phone: {settings.ADMISSION_CONTACT_PHONE}\n\n"
                        "Regards,\nAdmission Office\nMilitary College Murree"
                    )

                    email = EmailMessage(
                        subject="🎓 Roll Number Slip - Military College Murree",
                        body=email_body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[app.user.email],
                    )
                    email.send(fail_silently=True)
                except Exception as e:
                    logger.error(f"Email sending failed for {app.name}", exc_info=True)

                # Create notification
                try:
                    Notification.objects.create(
                        user=app.user,
                        title="Challan Verified",
                        message=f"🎉 Your challan has been verified. Roll Number: {app.roll_number}"
                    )
                except Exception as e:
                    logger.error(f"Notification error for {app.id}", exc_info=True)

                logger.info(f"Processed {app.name} ({app.roll_number})")

        except Exception as e:
            logger.error(f"Error verifying {app.name}", exc_info=True)
            continue