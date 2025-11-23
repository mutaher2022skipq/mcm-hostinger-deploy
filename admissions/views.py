from django.urls import reverse
from django.utils.dateparse import parse_date
from .models import FeeConfig, FeeCategoryConfig
from .utils import get_dynamic_fee_for_application, get_fee_by_category
from django.http import  Http404
from .tasks import bulk_verify_applications_task
from .tasks import broadcast_message_task
from django.templatetags.static import static
from django.core.mail import EmailMessage
from django.utils.html import strip_tags
from django.core.files.base import ContentFile
import threading, os
from django.core.paginator import Paginator
from django.db.models import Q
import json
from django.db.models import Count
from io import BytesIO
from django.templatetags.static import static
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
import logging

logger = logging.getLogger(__name__)
# admissions/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse
from datetime import date
import random
from django.contrib import messages
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from io import BytesIO

from .models import Application, AdmissionSession, FormFieldVisibility, MessageTemplate
from .forms import ApplicationForm
from django.core.mail import EmailMessage
import threading

# PDF libs
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
import io
from .utils import generate_roll_number_pdf
# notifications model (app 'notifications' should be installed)
from notifications.models import Notification
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.shortcuts import render
import csv
import pandas as pd

# --------------------------
# Helpers
# --------------------------
def staff_required(user):
    return user.is_staff or user.is_superuser


# ------------------------------
# Admin Fee Management Dashboard
# ------------------------------
@staff_member_required
@user_passes_test(staff_required)
def fee_management_dashboard(request):
    """
    Render and save fee configurations for a selected class (VIII or XI).
    GET: ?class=VIII or ?class=XI => show config
    POST: includes hidden selected_class => update config safely
    """

    from .models import FeeConfig, FeeCategoryConfig

    # Accept selected class from GET (when user selects) or from POST (when saving)
    selected_class = request.GET.get("class") or request.POST.get("selected_class")
    fee_config = None
    category_configs = None

    # If a class was provided, try to fetch the FeeConfig (may be None)
    if selected_class:
        try:
            fee_config = FeeConfig.objects.get(class_name=selected_class)
        except FeeConfig.DoesNotExist:
            fee_config = None

    # Handle save (POST)
    if request.method == "POST":
        if not selected_class:
            messages.error(request, "Please select a class before saving.")
            return redirect(reverse('admissions:fee_management'))

        # If fee_config does not exist, avoid raising and show friendly message.
        if not fee_config:
            messages.error(request, f"No FeeConfig exists for class {selected_class}. Create it first (admin).")
            return redirect(f"{reverse('admissions:fee_management')}?class={selected_class}")

        # --- parse and update deadlines (only when provided) ---
        nd = request.POST.get('normal_deadline', '').strip()
        ld = request.POST.get('late_deadline', '').strip()
        fd = request.POST.get('final_deadline', '').strip()

        # parse_date returns a datetime.date or None
        if nd:
            parsed = parse_date(nd)
            if parsed:
                fee_config.normal_deadline = parsed
        if ld:
            parsed = parse_date(ld)
            if parsed:
                fee_config.late_deadline = parsed
        if fd:
            parsed = parse_date(fd)
            if parsed:
                fee_config.final_deadline = parsed

        fee_config.stop_after_final = 'stop_after_final' in request.POST

        # CLASS XI: flat fees
        if fee_config.class_name == 'XI':
            try:
                base = request.POST.get('base_fee')
                double = request.POST.get('double_fee')
                triple = request.POST.get('triple_fee')
                if base is not None and base != '':
                    fee_config.base_fee = int(base)
                if double is not None and double != '':
                    fee_config.double_fee = int(double)
                if triple is not None and triple != '':
                    fee_config.triple_fee = int(triple)
            except ValueError:
                messages.warning(request, "Fee values must be numeric. Some values were ignored.")

        fee_config.save()

        # CLASS VIII: update category rows (if present)
        if fee_config.class_name == 'VIII':
            cats = FeeCategoryConfig.objects.filter(fee_config=fee_config)
            for cat in cats:
                # input names: normal_<id>, late_<id>, final_<id>
                n_key = f"normal_{cat.id}"
                l_key = f"late_{cat.id}"
                f_key = f"final_{cat.id}"
                try:
                    n_val = request.POST.get(n_key)
                    l_val = request.POST.get(l_key)
                    f_val = request.POST.get(f_key)
                    if n_val is not None and n_val != '':
                        cat.normal_fee = int(n_val)
                    if l_val is not None and l_val != '':
                        cat.late_fee = int(l_val)
                    if f_val is not None and f_val != '':
                        cat.final_fee = int(f_val)
                    cat.save()
                except ValueError:
                    # skip malformed values but continue
                    continue

        messages.success(request, "Fee configuration saved successfully.")
        # redirect back to same page (preserve query param)
        return redirect(f"{reverse('admissions:fee_management')}?class={selected_class}")

    # For GET: prepare category configs when needed
    if fee_config and fee_config.class_name == 'VIII':
        category_configs = FeeCategoryConfig.objects.filter(fee_config=fee_config).order_by('category')

    context = {
        "selected_class": selected_class,
        "fee_config": fee_config,
        "category_configs": category_configs,
        "page_title": "Fee Management Dashboard",
    }
    return render(request, "admin_portal/fees/fee_management.html", context)



@user_passes_test(staff_required)
def fee_config_edit(request, pk):
    config = get_object_or_404(FeeConfig, pk=pk)

    if request.method == "POST":
        config.normal_deadline = request.POST.get("normal_deadline") or config.normal_deadline
        config.late_deadline = request.POST.get("late_deadline") or config.late_deadline
        config.final_deadline = request.POST.get("final_deadline") or config.final_deadline
        config.stop_after_final = "stop_after_final" in request.POST

        if config.class_name == "XI":
            config.base_fee = int(request.POST.get("base_fee") or config.base_fee)
            config.double_fee = int(request.POST.get("double_fee") or config.double_fee)
            config.triple_fee = int(request.POST.get("triple_fee") or config.triple_fee)

        config.save()
        messages.success(request, "Fee configuration updated successfully.")
        return redirect("admissions:fee_management")

    return render(request, "admin_portal/fees/fee_config_edit.html", {"config": config})


@user_passes_test(staff_required)
def fee_category_edit(request, pk, cat_pk):
    config = get_object_or_404(FeeConfig, pk=pk)
    category = get_object_or_404(FeeCategoryConfig, pk=cat_pk, fee_config=config)

    if request.method == "POST":
        category.normal_fee = int(request.POST.get("normal_fee") or category.normal_fee)
        category.late_fee = int(request.POST.get("late_fee") or category.late_fee)
        category.final_fee = int(request.POST.get("final_fee") or category.final_fee)
        category.save()

        messages.success(request, "Category fee updated.")
        return redirect("admissions:fee_management")

    return render(
        request,
        "admin_portal/fees/fee_category_edit.html",
        {"config": config, "category": category},
    )


@user_passes_test(staff_required)
def fee_preview_ajax(request):
    """Returns computed fee for a selected date/class/category."""
    import datetime

    class_name = request.GET.get("class_name")
    category = request.GET.get("category")
    date_str = request.GET.get("date")

    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid date"})

    class Dummy:
        pass

    dummy = Dummy()
    dummy.class_name = class_name
    dummy.category = category

    try:
        amount, tier = get_dynamic_fee_for_application(dummy, as_of_date=d)
        return JsonResponse({"success": True, "amount": amount, "tier": tier})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})




#-----------------------
#Dymaic fees logic
#----------------------

@login_required
def print_challan(request):
    user = request.user
    try:
        application = Application.objects.get(user=user)
    except Application.DoesNotExist:
        return redirect('admissions:complete_form')

    # -----------------------------
    # NEW DYNAMIC FEE LOGIC
    # -----------------------------
    amount, tier = get_dynamic_fee_for_application(application)

    if tier == "closed":
        messages.error(request, "Admissions for this class are closed. Final deadline has passed.")
        return redirect("admissions:dashboard")

    # Fallback only if admin forgot to configure fee
    if amount is None:
        amount = 0

    # -----------------------------
    # Save challan fields
    # -----------------------------
    if not application.challan_no:
        application.challan_no = str(random.randint(10000, 99999))
    if not application.challan_date:
        application.challan_date = date.today()

    application.amount = amount
    application.save(update_fields=["amount", "challan_no", "challan_date"])

    # -----------------------------
    # Render challan template
    # -----------------------------
    context = {
        "application": application,
        "amount": amount,
        "tier": tier,  # normal | late | double | triple | final
        "is_late": tier != "normal",
    }
    return render(request, "admissions/print_challan.html", context)



# --------------------------
# Challan PDF download
# --------------------------
@login_required
def challan_pdf(request):
    user = request.user
    application = Application.objects.get(user=user)

    html = render_to_string('admissions/print_challan.html', {'application': application})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="challan_form.pdf"'

    from xhtml2pdf import pisa
    pisa.CreatePDF(html, dest=response)
    return response


# --------------------------
# Upload fee slip
# --------------------------
@login_required
def upload_fee_slip(request):
    user = request.user
    try:
        application = Application.objects.get(user=user)
    except Application.DoesNotExist:
        return redirect('admissions:complete_form')

    if request.method == 'POST':
        slip = request.FILES.get('payment_proof')
        if slip:
            application.payment_proof = slip
            application.payment_status = 'under_review'
            application.status = 'submitted'
            application.save()
            messages.success(request, "Your fee slip has been uploaded and is under review.")
            return redirect('admissions:dashboard')
        else:
            messages.error(request, "Please upload a file before submitting.")

    return render(request, 'admissions/upload_fee_slip.html', {'application': application})


# --------------------------
# Student dashboard
# --------------------------
@login_required
def dashboard(request):
    user = request.user

    # Redirect staff/admin to custom admin dashboard
    if user.is_staff or user.is_superuser:
        return redirect('admissions:admin_dashboard')

    # Load or create application
    application, created = Application.objects.get_or_create(user=user)
    if created:
        application.status = 'draft'
        application.save()

    # Progress mapping (unchanged)
    status_map = {
        'draft': (25, 'Draft'),
        'payment_pending': (50, 'Payment Pending'),
        'submitted': (75, 'Submitted'),
        'verified': (100, 'Verified'),
        'rejected': (100, 'Rejected'),
    }
    progress, label = status_map.get(application.status, (10, 'Not Started'))

    # ---------------------------------------------------
    # Ensure application.class_name is set / repaired early
    # so dashboard can immediately compute dynamic fee.
    # ---------------------------------------------------
    try:
        from .models import AdmissionSession
        user_class = getattr(user, 'class_applied', None)

        if user_class:
            try:
                session = AdmissionSession.objects.get(class_name=user_class)
                session_open = bool(session.is_open)
            except AdmissionSession.DoesNotExist:
                session_open = False

            # Case A: if application has no class -> set it (only if session open)
            if not application.class_name and session_open:
                application.class_name = user_class
                entry_year = date.today().year + 1
                application.entry = f"{application.class_name} Class Entry-{entry_year}"
                application.save(update_fields=['class_name', 'entry'])

            # Case B: application has a different class saved previously -> attempt safe fix
            elif application.class_name and application.class_name != user_class and session_open:
                # Only auto-fix when the target session is OPEN (safe to overwrite)
                application.class_name = user_class
                entry_year = date.today().year + 1
                application.entry = f"{application.class_name} Class Entry-{entry_year}"
                application.save(update_fields=['class_name', 'entry'])
    except Exception as e:
        # Don't crash dashboard for any unexpected error here
        logger.error("Session/class sync error on dashboard", exc_info=True)

    # ---------------------------------------
    # 🌟 Dynamic Fee (NEW FEE CONFIG SYSTEM)
    # ---------------------------------------
    amount = None
    fee_tier = None
    admissions_closed = False

    if getattr(application, 'class_name', None):
        try:
            amount, fee_tier = get_dynamic_fee_for_application(application)

            if fee_tier == "closed":
                admissions_closed = True
                amount = None   # show "closed" on UI
            else:
                # fallback to legacy category-based fee if helper returned None
                if amount is None:
                    amount = get_fee_by_category(application.category or 'civil')
        except Exception as e:
            logger.error("Fee calculation error on dashboard", exc_info=True)
            # safe fallback
            try:
                amount = get_fee_by_category(application.category or 'civil')
            except Exception:
                amount = None
                fee_tier = None

    # Notifications
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:10]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    context = {
        "application": application,
        "progress": progress,
        "label": label,

        # Dynamic Fee System
        "amount": amount,
        "fee_tier": fee_tier,
        "admissions_closed": admissions_closed,

        # UI
        "notifications": notifications,
        "unread_count": unread_count,
    }

    return render(request, "admissions/dashboard.html", context)





# --------------------------
# Complete application form (student)
# --------------------------
@login_required
def complete_application(request):
    user = request.user
    application, _ = Application.objects.get_or_create(user=user)

    # -----------------------------
    # Sync class_name ONLY if:
    # 1. application.class_name is empty, OR it's different from user's class_applied (we may fix),
    # 2. user.class_applied exists,
    # 3. AdmissionSession for that class is OPEN
    # -----------------------------
    from .models import AdmissionSession

    user_class = getattr(user, 'class_applied', None)

    if user_class:
        try:
            session = AdmissionSession.objects.get(class_name=user_class)
            session_open = bool(session.is_open)
        except AdmissionSession.DoesNotExist:
            session_open = False

        # Case A: Application has NO class assigned → set it (only if session open)
        if not application.class_name:
            if session_open:
                application.class_name = user_class
                entry_year = date.today().year + 1
                application.entry = f"{application.class_name} Class Entry-{entry_year}"
                application.save(update_fields=['class_name', 'entry'])
            else:
                # leave as-is; admin intentionally closed session
                logger.warning("Class session closed — class_name NOT auto-set")

        # Case B: Application has a different class saved previously → attempt safe fix
        elif application.class_name != user_class:
            # only overwrite if target session is open (safe repair)
            if session_open:
                logger.info(f"Fixing old wrong class '{application.class_name}' → '{user_class}'")
                application.class_name = user_class
                entry_year = date.today().year + 1
                application.entry = f"{application.class_name} Class Entry-{entry_year}"
                application.save(update_fields=['class_name', 'entry'])
            else:
                # do not change if target class session is closed
                logger.warning("Cannot fix class — target class session is closed")

    changed = False

    # -----------------------------
    # Prefill basic defaults
    # -----------------------------
    if not application.name:
        application.name = getattr(user, 'first_name', '') or user.username
        changed = True

    if not application.father_name:
        father_name = getattr(user, 'father_name', '') or request.session.get('father_name')
        if father_name:
            application.father_name = father_name
            changed = True

    if not application.dob and getattr(user, 'dob', None):
        application.dob = user.dob
        changed = True

    if not application.category:
        application.category = None
        changed = True

    if changed:
        application.save()

    # -----------------------------
    # Handle POST (form submit)
    # -----------------------------
    if request.method == 'POST':
        form = ApplicationForm(request.POST, request.FILES, instance=application)
        phone_number = request.POST.get('phone')  # template input

        if form.is_valid():
            app = form.save(commit=False)
            app.user = user

            # default status
            if app.status in ['draft', '', None]:
                app.status = 'payment_pending'

            # Military / Shaheed logic (preserve existing semantics)
            category = app.category or ""
            if category in ['offr_retired', 'jcos_retired']:
                if app.shaheed_status == "Yes" and app.shaheed_in:
                    if app.shaheed_in == "war_op":
                        app.admin_remarks = "Shaheed (War/Op)"
                        app.status_label = "shaheed"
                    else:
                        app.admin_remarks = "In Service Death"
                        app.status_label = "isd"
                else:
                    app.admin_remarks = ""
                    app.status_label = ""
            else:
                app.shaheed_status = None
                app.shaheed_in = None
                app.admin_remarks = ""
                app.status_label = ""

            # Ensure entry label reflects class_name & dynamic year
            entry_year = date.today().year + 1
            if app.class_name:
                app.entry = f"{app.class_name} Class Entry-{entry_year}"
            else:
                app.entry = f"Entry-{entry_year}"

            # Save mobile number on application (if provided)
            if phone_number:
                app.mobile_no = phone_number

            # Final save
            app.save()
            application.refresh_from_db()

            # Keep User.phone in sync if present on user model
            if phone_number and hasattr(user, 'phone') and phone_number != user.phone:
                user.phone = phone_number
                user.save(update_fields=['phone'])

            messages.success(request, "✅ Application updated successfully.")
            return redirect('admissions:view_application')

        else:
            logger.debug("Form errors: %s", form.errors.as_json())
            messages.error(request, "⚠️ Please fix the highlighted errors.")
    else:
        form = ApplicationForm(instance=application)

    # -----------------------------
    # Field visibility controls (unchanged)
    # -----------------------------
    for field_name in list(form.fields.keys()):
        FormFieldVisibility.objects.get_or_create(field_name=field_name, defaults={'is_visible': True})

    visible_fields = FormFieldVisibility.objects.filter(is_visible=True).values_list('field_name', flat=True)
    for field in list(form.fields.keys()):
        if field not in visible_fields:
            del form.fields[field]

    return render(request, 'admissions/complete_form.html', {
        'form': form,
        'user_phone': getattr(user, 'phone', '') or '',
        'application': application,
    })










# --------------------------
# View submitted application (read-only)
# --------------------------
@login_required
def view_application(request):
    try:
        application = Application.objects.get(user=request.user)
    except Application.DoesNotExist:
        return redirect('admissions:complete_form')

    return render(request, 'admissions/view_application.html', {'application': application})


# --------------------------
# Admin: list challans for verification
# --------------------------
@user_passes_test(staff_required)
def verify_challan_list(request):
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')

    challans = Application.objects.filter(payment_proof__isnull=False).order_by('-submission_date')

    if category_filter:
        challans = challans.filter(category=category_filter)
    if status_filter:
        challans = challans.filter(payment_status=status_filter)

    categories = Application.CATEGORY_CHOICES
    statuses = [
        ('under_review', 'Under Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending'),
    ]

    context = {
        'challans': challans,
        'categories': categories,
        'statuses': statuses,
        'category_filter': category_filter,
        'status_filter': status_filter,
    }
    return render(request, 'admissions/verify_challans.html', context)


# --------------------------
# AJAX: challan details modal
# --------------------------
@user_passes_test(staff_required)
def challan_details(request, app_id):
    try:
        app = Application.objects.get(id=app_id)
    except Application.DoesNotExist:
        return HttpResponse("<p class='text-red-600'>Application not found.</p>")
    return render(request, 'admissions/partials/challan_detail_modal.html', {'app': app})


# --------------------------
# Admin action: verify/reject challan (JSON)
# --------------------------
def verify_challan_action(request, app_id, action):
    """Handles verification or rejection of challan (individual)."""
    app = get_object_or_404(Application, id=app_id)

    if action == 'verify':
        app.payment_status = 'verified'
        app.status = 'verified'

        # Ensure roll number and secure token
        if not app.roll_number:
            app.roll_number = app.generate_roll_number()
        if not app.secure_token:
            import uuid
            app.secure_token = uuid.uuid4().hex[:12]

        try:
            # Generate PDF Roll Slip
            pdf_data = generate_roll_number_pdf(app)
            filename = f"RollSlip_{app.roll_number}.pdf"

            # Save PDF file (for dashboard download)
            if app.roll_slip:
                try:
                    app.roll_slip.delete(save=False)
                except Exception:
                    pass
            app.roll_slip.save(filename, ContentFile(pdf_data), save=False)
            app.save(update_fields=['roll_slip', 'payment_status', 'status', 'roll_number', 'secure_token'])

            # ✅ Build secure download link
            download_link = f"{request.scheme}://{request.get_host()}/admissions/download-roll-slip/{app.secure_token}/"

            # ✅ Email body (detailed)
            if app.class_name == 'XI':
                email_body = (
                    f"Dear {app.name},\n\n"
                    f"Your application has been verified successfully.\n\n"
                    f"Roll Number: {app.roll_number}\n"
                    f"Father’s Name: {app.father_name}\n"
                    f"Test Center: {app.get_test_center_display()}\n\n"
                    "📅 Examination Schedule:\n"
                    "• Report at respective center: 0800 hrs\n"
                    "• Start of written test: 0900 hrs\n"
                    "• Duration: 4 hours (till 1300 hrs)\n\n"
                    "🖊 Subjects: English, Mathematics, Physics, and Chemistry.\n\n"
                    "⚠ Important Instructions:\n"
                    "1. Bring your Roll Number Slip and writing material. Calculator is also allowed.\n"
                    "2. Entrance Exam booklet will be provided at the center.\n"
                    "3. Missing the test for any reason means no re-examination.\n"
                    "4. Mobile phones are not allowed.\n"
                    "5. Parents/Guardians must bring CNIC.\n\n"
                    f"👉 Download your Roll Number Slip securely here:\n{download_link}\n\n"
                    "Alternatively, log in to your MCM Admission Portal to download it anytime.\n\n"
                    f"For queries contact: {settings.ADMISSION_CONTACT_EMAIL} | Phone: {settings.ADMISSION_CONTACT_PHONE}\n\n"
                    "Regards,\nAdmission Office\nMilitary College Murree"
                )
            else:
                # Default for Class VIII
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

            threading.Thread(target=lambda e: e.send(fail_silently=True), args=(email,), daemon=True).start()

        except Exception as e:
            logger.error("Error generating/saving PDF or sending email", exc_info=True)

        # Create notification
        try:
            Notification.objects.create(
                user=app.user,
                title="Challan Verified",
                message=f"🎉 Your challan has been verified. Roll Number: {app.roll_number}"
            )
        except Exception as e:
            logger.error("Notification error", exc_info=True)

        message_text = f"✅ Challan for {app.name} verified successfully."

    elif action == 'reject':
        app.payment_status = 'rejected'
        app.status = 'rejected'
        app.save(update_fields=['payment_status', 'status'])

        # Notify student (in-app)
        try:
            Notification.objects.create(
                user=app.user,
                title="Challan Rejected",
                message="❌ Your challan has been rejected. Please contact the admission office."
            )
        except Exception as e:
            logger.error("Notification error", exc_info=True)

        # ✅ Send rejection email
        try:
            email_body = (
                f"Dear {app.name},\n\n"
                "We regret to inform you that your submitted challan could not be verified.\n\n"
                "Please ensure that all payment details were entered correctly and that the bank stamp "
                "or transaction slip is valid and readable.\n\n"
                "If you believe this was a mistake or have already resolved the issue, "
                "please contact the Admission Office at Military College Murree for clarification.\n\n"
                f"Contact: {settings.ADMISSION_CONTACT_EMAIL}\n"
                f"Phone: {settings.ADMISSION_CONTACT_PHONE}\n\n"
                "⏰ Office Hours: 08:00 AM – 02:00 PM (Mon–Fri)\n\n"
                "Thank you for your understanding.\n\n"
                "Regards,\nAdmission Office\nMilitary College Murree"
            )

            email = EmailMessage(
                subject="❌ Challan Rejected - Military College Murree",
                body=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[app.user.email],
            )

            threading.Thread(target=lambda e: e.send(fail_silently=True), args=(email,), daemon=True).start()

        except Exception as e:
            logger.error("Error sending rejection email", exc_info=True)

        message_text = f"❌ Challan for {app.name} rejected."

    # Return response
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'new_status': app.payment_status})
    else:
        messages.success(request, message_text)
        return redirect('admissions:admin_dashboard')





# --------------------------
# Admin Dashboard (analytics + admission session toggles)
# --------------------------
@user_passes_test(staff_required)
def admin_dashboard(request):
    """Custom Admin Dashboard — manages sessions, visibility, and applicants."""
    
    # Ensure sessions exist for each defined class
    for code, _ in AdmissionSession.CLASS_CHOICES:
        AdmissionSession.objects.get_or_create(class_name=code)

    # Handle toggle action
    if request.method == "POST" and request.POST.get("action") == "toggle_admission":
        class_name = request.POST.get("class_name")
        try:
            session = AdmissionSession.objects.get(class_name=class_name)
            session.is_open = not session.is_open
            session.save()
            messages.success(
                request,
                f"{session.get_class_name_display()} set to {'Open' if session.is_open else 'Closed'}."
            )
            return redirect('admissions:admin_dashboard')
        except AdmissionSession.DoesNotExist:
            messages.error(request, "Invalid class selected.")

    # Initialize FormFieldVisibility rows (if not present)
    for field in ApplicationForm().fields.keys():
        FormFieldVisibility.objects.get_or_create(field_name=field)

    # Applicant summary
    applications = Application.objects.select_related('user').all().order_by('-submission_date')
    total = applications.count()
    verified = applications.filter(status='verified').count()
    under_review = applications.filter(payment_status='under_review').count()
    pending = applications.filter(payment_status='pending').count()
    rejected = applications.filter(status='rejected').count()

    # Filters
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    if category_filter:
        applications = applications.filter(category=category_filter)
    if status_filter:
        applications = applications.filter(status=status_filter)

    sessions = AdmissionSession.objects.all().order_by('class_name')

    # ✅ Updated Context
    context = {
        'applications': applications,
        'total': total,
        'verified': verified,
        'under_review': under_review,
        'pending': pending,
        'rejected': rejected,
        'categories': Application.CATEGORY_CHOICES,     # ✅ for Category dropdown
        'test_centers': Application.TEST_CENTERS,       # ✅ for Test Center dropdown
        'category_filter': category_filter,
        'status_filter': status_filter,
        'sessions': sessions,
    }

    # ✅ Template path
    return render(request, 'admin_portal/admin_dashboard.html', context)

@user_passes_test(staff_required)
def admin_applicants_api(request):
    """
    Returns HTML snippet (table rows) for applicants filtered/searched by admin.
    Supports: q (search), center, status, date_from, date_to, class_name, page
    """
    qs = Application.objects.select_related('user').all().order_by('-submission_date')

    # 🔍 Search Filter
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(father_name__icontains=q) |
            Q(roll_number__icontains=q) |
            Q(form_b__icontains=q) |
            Q(father_cnic__icontains=q)
        )
    # 🏷 Category Filter  ⭐ ADD THIS ⭐
    category = request.GET.get('category', '').strip()
    if category:
        qs = qs.filter(category=category)

    # 🏫 Test Center Filter
    center = request.GET.get('center', '').strip()
    if center:
        qs = qs.filter(test_center=center)

    # 📌 Status Filter
    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    # 📅 Date Filters
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    if date_from:
        qs = qs.filter(submission_date__gte=date_from)
    if date_to:
        qs = qs.filter(submission_date__lte=date_to)

    # 🆕 📘 Class Filter (VIII | XI)
    cls = request.GET.get('class_name', '').strip()
    if cls:
        qs = qs.filter(class_name=cls)

    # 📄 Pagination
    page = int(request.GET.get('page', 1))
    per_page = 500
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page)

    # Render Ajax Partial
    html = render_to_string('admin_portal/partials/_applicant_rows.html', {
        'applications': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'request': request
    })
    return HttpResponse(html)



@user_passes_test(staff_required)
def bulk_applicant_action(request):
    """
    Bulk actions endpoint for admin:
       - action: 'verify' | 'reject' | 'assign_center'
       - ids[]: list of applicant ids
       - assign_center (if action == 'assign_center')
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=400)

    ids = request.POST.getlist('ids[]')
    action = request.POST.get('action')
    if not ids or not action:
        return JsonResponse({'success': False, 'error': 'missing params'}, status=400)

    apps = Application.objects.filter(id__in=ids)
    processed, errors = [], []

    # Contact details used in emails
    CONTACT_EMAIL = settings.ADMISSION_CONTACT_EMAIL
    CONTACT_PHONE = settings.ADMISSION_CONTACT_PHONE

    # ----------------------
    # BULK VERIFY
    # ----------------------
    if action == 'verify':
        def verify_worker(to_verify_qs, admin_user=None):
            for app in to_verify_qs:
                try:
                    app.payment_status = 'verified'
                    app.status = 'verified'

                    # Generate roll number and secure token
                    if not app.roll_number:
                        app.roll_number = app.generate_roll_number()
                    if not app.secure_token:
                        import uuid
                        app.secure_token = uuid.uuid4().hex[:12]

                    app.save(update_fields=['payment_status', 'status', 'roll_number', 'secure_token'])

                    # Generate Roll Slip PDF
                    try:
                        pdf_data = generate_roll_number_pdf(app)
                        filename = f"RollSlip_{app.roll_number}.pdf"
                        if app.roll_slip:
                            try:
                                app.roll_slip.delete(save=False)
                            except Exception:
                                pass
                        app.roll_slip.save(filename, ContentFile(pdf_data), save=False)
                        app.save(update_fields=['roll_slip'])
                    except Exception as e:
                        logger.error(f"PDF generation error for {app.id}", exc_info=True)

                    # Build secure download link
                    download_link = f"{request.scheme}://{request.get_host()}/admissions/download-roll-slip/{app.secure_token}/"

                    # Detailed verification email (same content as verify_challan_action with phone)
                    if app.class_name == 'XI':
                        email_body = (
                            f"Dear {app.name},\n\n"
                            f"Your application has been verified successfully.\n\n"
                            f"Roll Number: {app.roll_number}\n"
                            f"Father’s Name: {app.father_name}\n"
                            f"Test Center: {app.get_test_center_display()}\n\n"
                            "📅 Examination Schedule:\n"
                            "• Report at respective center: 0800 hrs\n"
                            "• Start of written test: 0900 hrs\n"
                            "• Duration: 4 hours (till 1300 hrs)\n\n"
                            "🖊 Subjects: English, Mathematics, Physics, and Chemistry.\n\n"
                            "⚠ Important Instructions:\n"
                            "1. Bring your Roll Number Slip and writing material. Calculator is also allowed.\n"
                            "2. Entrance Exam booklet will be provided at the center.\n"
                            "3. Missing the test for any reason means no re-examination.\n"
                            "4. Mobile phones are not allowed.\n"
                            "5. Parents/Guardians must bring CNIC.\n\n"
                            f"👉 Download your Roll Number Slip securely here:\n{download_link}\n\n"
                            "Alternatively, log in to your MCM Admission Portal to download it anytime.\n\n"
                            f"For queries contact: {CONTACT_EMAIL} | Phone: {CONTACT_PHONE}\n\n"
                            "Regards,\nAdmission Office\nMilitary College Murree"
                        )
                    else:
                        # Default for Class VIII
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
                            f"For queries contact: {CONTACT_EMAIL} | Phone: {CONTACT_PHONE}\n\n"
                            "Regards,\nAdmission Office\nMilitary College Murree"
                        )

                    email = EmailMessage(
                        subject="🎓 Roll Number Slip - Military College Murree",
                        body=email_body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[app.user.email],
                    )

                    # Send in background
                    threading.Thread(target=lambda e: e.send(fail_silently=True), args=(email,), daemon=True).start()

                    # Notification
                    try:
                        Notification.objects.create(
                            user=app.user,
                            title="Challan Verified",
                            message=f"🎉 Your challan has been verified. Roll Number: {app.roll_number}"
                        )
                    except Exception as e:
                        logger.error(f"Notification error for {app.id}", exc_info=True)

                    processed.append(str(app.id))

                except Exception as ex:
                    errors.append(str(ex))
        from .tasks import bulk_verify_applications_task

        # Get absolute base URL (for secure link building)
        base_url = f"{request.scheme}://{request.get_host()}"
        apps.update(
        status='verified',
        payment_status='verified'
        )

        # Trigger Celery task instead of thread
        try:
            bulk_verify_applications_task.delay(
                list(apps.values_list('id', flat=True)),
                f"{request.scheme}://{request.get_host()}"
            )
        except Exception as e:
            logger.warning("Celery task failed, fallback to threaded worker", exc_info=True)
            threading.Thread(target=verify_worker, args=(list(apps), request.user), daemon=True).start()

    # ----------------------
    # BULK REJECT
    # ----------------------
    elif action == 'reject':
        apps.update(payment_status='rejected', status='rejected')

        def reject_worker(rejected_qs):
            for app in rejected_qs:
                try:
                    # Create in-app notification
                    try:
                        Notification.objects.create(
                            user=app.user,
                            title="Challan Rejected",
                            message="❌ Your challan has been rejected. Please contact the admission office for further assistance."
                        )
                    except Exception:
                        pass

                    # Rejection email (polite, include contact phone & email)
                    email_body = (
                        f"Dear {app.name},\n\n"
                        "We regret to inform you that your submitted challan could not be verified.\n\n"
                        "Please ensure that all payment details were entered correctly and that the bank stamp "
                        "or transaction slip is valid and readable.\n\n"
                        "If you believe this was a mistake or have already resolved the issue, "
                        "please contact the Admission Office at Military College Murree for clarification.\n\n"
                        f"Contact: {CONTACT_EMAIL}\n"
                        f"Phone: {CONTACT_PHONE}\n\n"
                        "⏰ Office Hours: 08:00 AM – 02:00 PM (Mon–Fri)\n\n"
                        "Thank you for your understanding.\n\n"
                        "Regards,\nAdmission Office\nMilitary College Murree"
                    )

                    email = EmailMessage(
                        subject="❌ Challan Rejected - Military College Murree",
                        body=email_body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[app.user.email],
                    )

                    threading.Thread(target=lambda e: e.send(fail_silently=True), args=(email,), daemon=True).start()

                    processed.append(str(app.id))

                except Exception as e:
                    errors.append(str(e))

        threading.Thread(target=reject_worker, args=(list(apps),), daemon=True).start()

    # ----------------------
    # ASSIGN CENTER
    # ----------------------
    elif action == 'assign_center':
        center = request.POST.get('assign_center', '').strip()
        if not center:
            return JsonResponse({'success': False, 'error': 'assign_center required'}, status=400)
        apps.update(test_center=center)
        processed = [str(a.id) for a in apps]

    else:
        return JsonResponse({'success': False, 'error': 'unknown action'}, status=400)

    return JsonResponse({'success': True, 'processed': processed, 'errors': errors})



@staff_member_required
def view_applicant(request, app_id):
    """Display full details of one applicant for admin review."""
    app = get_object_or_404(Application, id=app_id)
    return render(request, 'admin_portal/applicant_detail.html', {'app': app})

# --------------------------
# Admin: manage field visibility
# --------------------------
@user_passes_test(staff_required)
def form_field_control(request):
    fields = FormFieldVisibility.objects.all().order_by('field_name')
    if request.method == "POST":
        for field in fields:
            field.is_visible = field.field_name in request.POST.getlist("visible_fields")
            field.save()
        messages.success(request, "Form field visibility updated successfully!")
        return redirect('admissions:form_field_control')
    return render(request, 'admissions/form_field_control.html', {'fields': fields})


# --------------------------
# Admin: preview fee slip image (separate endpoint)
# --------------------------
@user_passes_test(staff_required)
def view_fee_slip(request, app_id):
    app = get_object_or_404(Application, id=app_id)
    return render(request, 'admissions/partials/view_fee_slip.html', {'app': app})


# --------------------------
# Toggle admission endpoint (used by admin buttons)
# --------------------------
@user_passes_test(staff_required)
def toggle_admission(request, session_id):
    if request.method == "POST":
        session = get_object_or_404(AdmissionSession, id=session_id)
        session.is_open = not session.is_open
        session.save()
        status = "opened" if session.is_open else "closed"
        messages.success(request, f"✅ Admission for {session.get_class_name_display()} has been {status}.")
    return redirect('admissions:admin_dashboard')
from django.http import FileResponse, Http404

@login_required
def download_roll_slip_dashboard(request):
    """Allows verified applicants to download their roll number slip PDF."""
    try:
        app = request.user.admission_application
    except Application.DoesNotExist:
        raise Http404("Application not found.")

    if app.status != 'verified':
        messages.warning(request, "Your roll number slip will be available after verification.")
        return redirect('admissions:dashboard')

    # Regenerate if missing
    if not app.roll_slip or not os.path.exists(app.roll_slip.path):
        pdf_data = generate_roll_number_pdf(app)
        pdf_filename = f"RollSlip_{app.roll_number or 'Pending'}.pdf"
        pdf_path = os.path.join(settings.MEDIA_ROOT, 'roll_slips', pdf_filename)

        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(pdf_data)

        app.roll_slip.name = f"roll_slips/{pdf_filename}"
        app.save(update_fields=['roll_slip'])

    return FileResponse(
        open(app.roll_slip.path, 'rb'),
        as_attachment=True,
        filename=os.path.basename(app.roll_slip.name)
    )
def download_roll_slip(request, token):
    """Securely serve roll slip PDFs to verified applicants using unique tokens."""
    try:
        app = Application.objects.get(secure_token=token, status='verified')
        if not app.roll_slip:
            raise Http404("Roll slip not found.")

        return FileResponse(
            open(app.roll_slip.path, 'rb'),
            as_attachment=True,
            filename=f"RollSlip_{app.roll_number}.pdf"
        )
    except Application.DoesNotExist:
        raise Http404("Invalid or expired download link.")
# ────────────────────────────────────────────────────────────────
# 📊 PHASE 2 — ADMIN ANALYTICS DASHBOARD (Chart.js Integration)
# ────────────────────────────────────────────────────────────────
# This section powers the visual analytics panel on the admin dashboard.
# It provides JSON data endpoints that Chart.js uses to render:
#   • Applicants by Category (Pie Chart)
#   • Applicants by Status (Donut Chart)
#   • Applicants by Test Center (Bar Chart)
#   • Daily Submissions (Line Chart)
#
# Usage:
#   - Frontend (admin_dashboard.html) fetches data via AJAX from this endpoint.
#   - Data is dynamically rendered with Chart.js charts.
#
# Developer Notes:
#   ✅ Uses Django ORM aggregation (annotate + Count)
#   ✅ Lightweight — returns clean JSON for fast client-side rendering
#   ✅ Ready for future filters (date range, center, etc.)
# ────────────────────────────────────────────────────────────────



@user_passes_test(staff_required)
def analytics_data(request):
    """Return aggregated analytics data for admin dashboard charts."""
    try:
        data = {
            'by_category': list(
                Application.objects
                .values('category')
                .annotate(count=Count('id'))
                .order_by('category')
            ),
            'by_status': list(
                Application.objects
                .values('status')
                .annotate(count=Count('id'))
                .order_by('status')
            ),
            'by_center': list(
                Application.objects
                .values('test_center')
                .annotate(count=Count('id'))
                .order_by('test_center')
            ),
            'daily_submissions': list(
                Application.objects
                .extra({'date': "date(submission_date)"})
                .values('date')
                .annotate(count=Count('id'))
                .order_by('date')
            ),
        }
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@user_passes_test(staff_required)
def admin_analytics(request):
    """Renders the analytics dashboard page."""
    return render(request, 'admin_portal/admin_analytics.html')

@user_passes_test(staff_required)
def export_analytics_pdf(request):
    """Generate the Admission Analytics PDF report."""

    # --- Analytics logic ---
    total = Application.objects.count()
    verified = Application.objects.filter(status='verified').count()
    under_review = Application.objects.filter(payment_status='under_review').count()
    pending = Application.objects.filter(payment_status='pending').count()
    rejected = Application.objects.filter(status='rejected').count()

    # Query data
    by_category = Application.objects.values('category').annotate(count=Count('id')).order_by('category')
    by_status = Application.objects.values('status').annotate(count=Count('id')).order_by('status')
    by_center = Application.objects.values('test_center').annotate(count=Count('id')).order_by('test_center')
    daily_submissions = (
        Application.objects.extra({'date': "date(submission_date)"})
        .values('date')
        .annotate(count=Count('id'))
        .order_by('-date')
    )

    # ✅ Build logo URL for WeasyPrint
    logo_url = request.build_absolute_uri(static('images/logo.png'))

    context = {
        'total': total,
        'verified': verified,
        'under_review': under_review,
        'pending': pending,
        'rejected': rejected,
        'by_category': by_category,
        'by_status': by_status,
        'by_center': by_center,
        'daily_submissions': daily_submissions,
        'timestamp': datetime.now(),  # ✅ fixed here
        'logo_url': logo_url,
    }

    html_string = render_to_string('admin_portal/analytics_pdf_template.html', context)
    
    # Use xhtml2pdf instead of weasyprint (no system dependencies required)
    try:
        from xhtml2pdf import pisa
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="MCM_Analytics_Report.pdf"'
        pisa.CreatePDF(html_string, dest=response)
        return response
    except ImportError:
        # Fallback: return HTML if PDF generation fails
        return HttpResponse(html_string, content_type='text/html')


#---------------------------------
# Export filter data 
#---------------------------------

@user_passes_test(staff_required)
def export_applicants_csv(request):
    """Exports filtered applicants as CSV."""
    queryset = get_filtered_applicants(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="MCM_Applicants.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Name', 'Father Name', 'Mobile Number', 'Category', 'Shaheed Status', 'Status', 'Payment',
        'Test Center', 'Roll Number',
        'Class Applied',
        '9th %', '10th %',
        '9th Marksheet URL',
        '10th Marksheet URL'
    ])

    for app in queryset:

        # ⭐ Shaheed status logic
        if app.admin_remarks:
            remarks = app.admin_remarks.lower()
            if "shaheed" in remarks:
                shaheed_status = "Shaheed"
            elif "in service death" in remarks:
                shaheed_status = "In Service Death"
            else:
                shaheed_status = ""
        else:
            shaheed_status = ""

        writer.writerow([
            app.name,
            app.father_name,
            app.user.phone,  # Corrected: Use phone field
            app.get_category_display(),
            shaheed_status,                 # ⭐ NEW COLUMN
            app.status,
            app.payment_status,
            app.get_test_center_display(),
            app.roll_number or '',
            app.class_name or '',
            app.percentage_9th or '',
            app.percentage_10th or '',
            app.marksheet_9th.url if app.marksheet_9th else '',
            app.marksheet_10th.url if app.marksheet_10th else ''
        ])

    return response

@user_passes_test(staff_required)
def export_applicants_excel(request):
    """Exports filtered applicants as Excel."""
    queryset = get_filtered_applicants(request)

    data = []
    for app in queryset:

        # ⭐ Shaheed status logic
        if app.admin_remarks:
            remarks = app.admin_remarks.lower()
            if "shaheed" in remarks:
                shaheed_status = "Shaheed"
            elif "in service death" in remarks:
                shaheed_status = "In Service Death"
            else:
                shaheed_status = ""
        else:
            shaheed_status = ""

        data.append({
            'Name': app.name,
            'Father Name': app.father_name,
            'Mobile Number': app.user.phone,  # Corrected: Use phone field
            'Category': app.get_category_display(),

            # ⭐ NEW COLUMN
            'Shaheed Status': shaheed_status,

            'Status': app.status,
            'Payment': app.payment_status,
            'Test Center': app.get_test_center_display(),
            'Roll Number': app.roll_number or '',
            'Class Applied': app.class_name or '',

            '9th %': app.percentage_9th or '',
            '10th %': app.percentage_10th or '',

            '9th Marksheet URL': (
                app.marksheet_9th.url if app.marksheet_9th else ''
            ),
            '10th Marksheet URL': (
                app.marksheet_10th.url if app.marksheet_10th else ''
            )
        })

    df = pd.DataFrame(data)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Applicants')

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="MCM_Applicants.xlsx"'
    return response




def get_filtered_applicants(request):
    """Unified filtering for dashboard, CSV export, Excel export."""

    qs = Application.objects.all()

    # 🔍 Search
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(father_name__icontains=q) |
            Q(roll_number__icontains=q) |
            Q(form_b__icontains=q) |
            Q(father_cnic__icontains=q)
        )

    # 🏷 Category
    category = request.GET.get('category', '').strip()
    if category:
        qs = qs.filter(category=category)

    # 📌 Status
    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    # 🏫 Center
    center = request.GET.get('center', '').strip()
    if center:
        qs = qs.filter(test_center=center)

    # 📘 Class (VIII | XI)
    class_name = request.GET.get('class_name', '').strip()
    if class_name:
        qs = qs.filter(class_name=class_name)

    # 📅 Date From/To
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if date_from:
        qs = qs.filter(submission_date__date__gte=date_from)
    if date_to:
        qs = qs.filter(submission_date__date__lte=date_to)

    # ⭐ NEW — SHAHEED FILTER
    shaheed_filter = request.GET.get("shaheed", "").strip()

    if shaheed_filter == "shaheed":
        qs = qs.filter(admin_remarks__icontains="shaheed")

    elif shaheed_filter == "isd":
        qs = qs.filter(admin_remarks__icontains="in service death")

    elif shaheed_filter == "normal":
        qs = qs.exclude(admin_remarks__icontains="shaheed") \
               .exclude(admin_remarks__icontains="in service death")

    return qs.order_by('-submission_date')



 


#-------------------------------------------------------
#   Broadcast section message/Preview
#-------------------------------------------------------
@login_required
@user_passes_test(staff_required)
def broadcast_messages(request):
    templates = MessageTemplate.objects.all().order_by('-created_at')
    sent = False

    if request.method == 'POST':
        template_id = request.POST.get('template_id')
        send_email = 'send_email' in request.POST
        send_inapp = 'send_inapp' in request.POST

        template = MessageTemplate.objects.get(id=template_id)

        # ✅ Use Celery (or threaded fallback automatically)
        try:
            broadcast_message_task.delay(template.id, send_email, send_inapp)
        except Exception:
            # fallback to direct call (threaded mode)
            broadcast_message_task(template.id, send_email, send_inapp)

        sent = True

    return render(request, 'admin_portal/broadcast_messages.html', {'templates': templates, 'sent': sent})

@login_required
@user_passes_test(staff_required)
def broadcast_preview(request):
    """
    Live preview of selected message template before broadcast.
    """
    from django.templatetags.static import static

    template_id = request.GET.get('template_id')
    if template_id:
        try:
            template = MessageTemplate.objects.get(id=template_id)
            subject = template.subject or template.title
            body = template.body
        except MessageTemplate.DoesNotExist:
            subject = "Invalid Template"
            body = "The selected template could not be found."
    else:
        subject = "Preview Example: Reporting Instructions"
        body = (
            "Dear Cadet,\n\n"
            "Your reporting date for entrance exam is 15 January 2026.\n"
            "Please bring your Roll Slip and CNIC copy.\n\n"
            "Regards,\n"
            "Admission Office\nMilitary College Murree"
        )

    logo_url = request.build_absolute_uri(static('images/logo.png'))

    return render(request, 'emails/broadcast_template.html', {
        'subject': subject,
        'body': body,
        'logo_url': logo_url,
        'name': "Cadet Name"
    })


@user_passes_test(staff_required)
def create_message_template(request):
    """
    Create new message template via AJAX (from broadcast page modal).
    """
    if request.method == "POST":
        title = request.POST.get("title")
        category = request.POST.get("category")
        subject = request.POST.get("subject")
        body = request.POST.get("body")

        if not title or not body:
            return JsonResponse({"success": False, "error": "Title and Body are required."})

        template = MessageTemplate.objects.create(
            title=title,
            category=category,
            subject=subject,
            body=body,
            created_by=request.user
        )

        return JsonResponse({
            "success": True,
            "id": template.id,
            "title": template.title,
            "category": template.get_category_display()
        })

    return JsonResponse({"success": False, "error": "Invalid request method"})