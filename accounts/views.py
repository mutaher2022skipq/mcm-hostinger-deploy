# accounts/views.py
from datetime import timedelta, date
import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_backends, login
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

from .forms import ClassSelectionForm, StudentSignupForm
from .models import EmailVerification, User

# -------------------------------------------------------
# AGE CALCULATOR (added safely above everything)
# -------------------------------------------------------
def calculate_age_on(dob, ref_date):
    return (
        ref_date.year - dob.year
        - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
    )


# --------------------------
# STEP 1 – CLASS & DOB
# --------------------------
def signup_step1(request):
    """Step 1 - Select class and DOB (only open classes are shown)."""
    from admissions.models import AdmissionSession, FormFieldVisibility

    open_classes = list(AdmissionSession.objects.filter(is_open=True).values_list('class_name', flat=True))

    if not open_classes:
        messages.warning(request, "⚠️ Currently, no class admissions are open.")
        return render(request, 'accounts/signup_closed.html')

    if request.method == 'POST':
        form = ClassSelectionForm(request.POST)
        if form.is_valid():

            selected_class = form.cleaned_data['class_applied']
            dob = form.cleaned_data['dob']

            if selected_class not in open_classes:
                messages.error(request, "❌ Admissions for this class are closed.")
                return redirect('accounts:signup_step1')

            # -------------------------------------------------------
            # AGE VALIDATION LOGIC (Precise Month-Based)
            # -------------------------------------------------------
            today = date.today()

            # Dynamic Admission Year Logic:
            # If Jul-Dec (Month >= 7) -> Assume applying for Next Year (e.g., Jul 2026 -> 2027)
            # If Jan-Jun (Month < 7)  -> Assume applying for Current Year (e.g., Jan 2027 -> 2027)
            if today.month >= 7:
                admission_year = today.year + 1
            else:
                admission_year = today.year

            def get_age_in_months(dob, ref_date):
                months = (ref_date.year - dob.year) * 12 + (ref_date.month - dob.month)
                if ref_date.day < dob.day:
                    months -= 1
                return months

            # CLASS XI – 14y 9m to 17y 3m on 1st July
            if selected_class == 'XI':
                cutoff_date = date(admission_year, 7, 1)
                age_months = get_age_in_months(dob, cutoff_date)

                # 14y 9m = 177 months, 17y 3m = 207 months
                if not (177 <= age_months <= 207):
                    messages.error(
                        request,
                        f"For Class XI, age must be between 14 years 9 months and 17 years 3 months on "
                        f"{cutoff_date.strftime('%d %B %Y')}."
                    )
                    return redirect('accounts:signup_step1')

            # CLASS VIII – 11y 9m to 14y 3m on 1st April
            elif selected_class == 'VIII':
                cutoff_date = date(admission_year, 4, 1)
                age_months = get_age_in_months(dob, cutoff_date)

                # 11y 9m = 141 months, 14y 3m = 171 months
                if not (141 <= age_months <= 171):
                    messages.error(
                        request,
                        f"For Class VIII, age must be between 11 years 9 months and 14 years 3 months on "
                        f"{cutoff_date.strftime('%d %B %Y')}."
                    )
                    return redirect('accounts:signup_step1')

            # -------------------------------------------------------
            # Existing logic continues (unchanged)
            # -------------------------------------------------------
            request.session['class_applied'] = selected_class
            request.session['dob'] = str(dob)
            return redirect('accounts:signup_step2')

    else:
        form = ClassSelectionForm()

        visible_fields = list(
            FormFieldVisibility.objects.filter(is_visible=True).values_list('field_name', flat=True)
        )

        if 'class_applied' in form.fields:
            form.fields['class_applied'].choices = [
                (cls, f"Class {cls.upper()}") for cls in open_classes
            ]

        for field in list(form.fields.keys()):
            if field not in visible_fields and field not in ['class_applied', 'dob']:
                del form.fields[field]

    return render(request, 'accounts/signup_step1.html', {'form': form, 'open_classes': open_classes})


# --------------------------
# STEP 2 – PERSONAL INFO
# --------------------------
def signup_step2(request):
    class_applied = request.session.get('class_applied')
    dob = request.session.get('dob')

    if not class_applied or not dob:
        return redirect('accounts:signup_step1')

    if request.method == 'POST':
        form = StudentSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.class_applied = class_applied
            user.dob = dob
            user.role = 'student'
            user.is_active = False
            user.save()

            request.session['pending_email'] = user.email
            request.session['pending_class_applied'] = class_applied

            send_verification_email(user)
            messages.info(request, "📩 A verification code has been sent to your email.")
            return redirect('accounts:verify_email')
    else:
        form = StudentSignupForm()

    return render(request, 'accounts/signup_step2.html', {'form': form, 'class_applied': class_applied, 'dob': dob})


# --------------------------
# EMAIL VERIFICATION LOGIC
# --------------------------
def send_verification_email(user):
    code = str(random.randint(100000, 999999))
    EmailVerification.objects.create(user=user, code=code)

    send_mail(
        subject='Verify your MCM Admission account',
        message=f'Your email verification code is: {code}\n\nFor any queries, contact mcm.admission.portal@gmail.com | Phone: 051-3752010.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def verify_email(request):
    if request.method == "POST":
        code = request.POST.get("code")
        verification = EmailVerification.objects.filter(code=code, is_used=False).first()

        if verification:
            verification.is_used = True
            verification.save()

            user = verification.user
            user.is_active = True

            pending_class = request.session.get('pending_class_applied')
            if pending_class:
                user.class_applied = pending_class

            user.save()

            request.session.pop('class_applied', None)
            request.session.pop('dob', None)
            request.session.pop('pending_class_applied', None)
            request.session.pop('pending_email', None)

            backend = get_backends()[0]
            user.backend = f"{backend.__module__}.{backend.__class__.__name__}"

            login(request, user)
            messages.success(request, "✅ Email verified successfully! Welcome aboard.")
            return redirect("admissions:dashboard")
        else:
            messages.error(request, "❌ Invalid or expired verification code. Try again.")

    remaining = request.session.get('remaining_seconds', 0)
    return render(request, "accounts/verify_email.html", {'remaining_seconds': remaining})


# --------------------------
# RESEND CODE
# --------------------------
def resend_code(request):
    email = request.session.get('pending_email') or (request.user.email if request.user.is_authenticated else None)

    if not email:
        messages.error(request, "⚠️ Unable to identify your account. Please log in or sign up again.")
        return redirect("accounts:login")

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, "❌ No account found with this email.")
        return redirect("accounts:signup_step1")

    last_sent = request.session.get('last_code_sent')
    if last_sent:
        elapsed = timezone.now() - timezone.datetime.fromisoformat(last_sent)
        if elapsed < timedelta(seconds=60):
            remaining = 60 - int(elapsed.total_seconds())
            request.session['remaining_seconds'] = remaining
            messages.warning(request, f"⏳ Please wait {remaining}s before resending again.")
            return redirect("accounts:verify_email")

    EmailVerification.objects.filter(user=user, is_used=False).delete()

    new_code = str(random.randint(100000, 999999))
    EmailVerification.objects.create(user=user, code=new_code)

    send_mail(
        subject="Your New MCM Admission Verification Code",
        message=f"Here is your new email verification code: {new_code}\n\nFor any queries, contact mcm.admission.portal@gmail.com | Phone: 051-3752010.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    request.session['pending_email'] = user.email
    request.session['last_code_sent'] = timezone.now().isoformat()
    request.session['remaining_seconds'] = 60

    messages.success(request, "✅ A new verification code has been sent to your email.")
    return redirect("accounts:verify_email")


# --------------------------
# LOGIN / LOGOUT
# --------------------------
@method_decorator(csrf_protect, name='dispatch')
class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'

    def post(self, request, *args, **kwargs):
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')

        user = None
        try:
            user = User.objects.get(email=username_or_email)
        except User.DoesNotExist:
            try:
                user = User.objects.get(username=username_or_email)
            except User.DoesNotExist:
                user = None

        if user and not user.is_active:
            request.session['pending_email'] = user.email
            messages.warning(request, "⚠️ Your account is not verified yet. Please check your email for the verification code.")
            return redirect('accounts:verify_email')

        user = authenticate(request, username=username_or_email, password=password)
        if user is None:
            messages.error(request, "❌ Invalid username/email or password.")
            return self.get(request, *args, **kwargs)

        login(request, user)
        messages.success(request, "✅ Logged in successfully.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return reverse_lazy('admissions:admin_dashboard')
        return reverse_lazy('admissions:dashboard')


class CustomLogoutView(LogoutView):
    next_page = '/accounts/login/'

    def dispatch(self, request, *args, **kwargs):
        messages.success(request, "👋 You’ve been logged out successfully.")
        return super().dispatch(request, *args, **kwargs)



