from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
import uuid
import random

from django.core.exceptions import ValidationError
from datetime import date

# --------------------------
# File Validator (FOR XI)
# --------------------------
def validate_marksheet(file):
    max_mb = 5
    if file.size > max_mb * 1024 * 1024:
        raise ValidationError(f"File size must be ≤ {max_mb} MB")

    allowed = ['pdf', 'jpg', 'jpeg', 'png']
    ext = file.name.split('.')[-1].lower()
    if ext not in allowed:
        raise ValidationError("Allowed formats: PDF, JPG, JPEG, PNG")


# --------------------------
# Photo Validator
# --------------------------
def validate_photo(file):
    max_mb = 2  # 2MB limit for photos
    if file.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Photo size must be ≤ {max_mb} MB")
    
    allowed = ['jpg', 'jpeg', 'png']
    ext = file.name.split('.')[-1].lower()
    if ext not in allowed:
        raise ValidationError("Allowed formats: JPG, JPEG, PNG")


YES_NO_CHOICES = [
    ('Yes', 'Yes'),
    ('No', 'No'),
]


class Application(models.Model):

    # --------------------------
    # Status Choices
    # --------------------------
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('payment_pending', 'Payment Pending'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    CATEGORY_CHOICES = [
        ('offr_serving', 'Offrs (Serving)'),
        ('offr_retired', 'Offrs (Retired)'),
        ('jcos_serving', 'JCOs/Sldrs (Serving)'),
        ('jcos_retired', 'JCOs/Sldrs (Retired)'),
        ('caf', 'CAF (FC KPK / Punjab Ranger)'),
        ('civilian', 'Civilians'),
        ('fata', 'FATA'),
        ('balochistan', 'BALOCHISTAN'),
        ('gilgit', 'Gilgit Baltistan'),
        ('ajk', 'AJ&K'),
        ('navy_airforce', 'Personnel of Navy / Airforce'),
    ]

    TEST_CENTERS = [
        ('Peshawar', 'Peshawar – FG Degree College for Men, School Road, Peshawar Cantt'),
        ('Abbottabad', 'Abbottabad – Education School, Baloch Centre, Abbottabad'),
        ('Rawalpindi1', 'Rawalpindi 1 – Military College of Signals, Rawalpindi'),
        ('Rawalpindi2', 'Rawalpindi 2 – EME College, Rawalpindi'),
        ('Jhelum', 'Jhelum – Military College Jhelum'),
        ('Lahore', 'Lahore – Garrison Boys High School (APS Sarfraz Rafiqui Road), Lahore Cantt'),
        ('Sialkot', 'Sialkot – FG Public High School, Sialkot'),
        ('Multan', 'Multan – FG Degree College for Boys, Qasim Bela Road, Multan Cantt'),
        ('Hyderabad', 'Hyderabad – Station Central School / HRDC, Hyderabad'),
        ('Quetta', 'Quetta – HRDC 33 Div, Khalid Road, Quetta'),
        ('Karachi', 'Karachi – Garrison HRDC, 5 Corps, Malir Cantt'),
        ('Sargodha', 'Sargodha – Army Public School, Sargodha'),
        ('Pano Aqil', 'Pano Aqil – Garrison HRDC, Pano Aqil'),
        ('Muzaffarabad', 'Muzaffarabad – Garrison HRDC, Muzaffarabad'),
        ('Gilgit', 'Gilgit – Army Public School, Jutial, Gilgit'),
        ('Murree', 'Murree – Military College Murree'),
    ]

    # -------------------------------------------------
    # Core Fields
    # -------------------------------------------------
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admission_application'
    )

    # Keep permanent record of which class this application is for
    class_name = models.CharField(
        max_length=10,
        choices=[('VIII', 'Class VIII'), ('XI', 'Class XI')],
        default='VIII'
    )

    photo = models.ImageField(upload_to='photos/', blank=True, null=True, validators=[validate_photo])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submission_date = models.DateField(default=timezone.now)
    challan_image = models.ImageField(upload_to='challans/', blank=True, null=True)
    admin_remarks = models.TextField(blank=True, null=True)

    # -------------------------------------------------
    # Fee Information
    # -------------------------------------------------
    total_fee = models.PositiveIntegerField(default=3000)
    amount = models.PositiveIntegerField(default=0)
    payment_proof = models.ImageField(upload_to='fee_slips/', blank=True, null=True)
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('under_review', 'Under Review'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ],
        default='pending'
    )

    fee_type = models.CharField(max_length=20, default='Single')
    entry = models.CharField(max_length=100, default='8th Class Entry-2026')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True, null=True)

    # -------------------------------------------------
    # Personal Details
    # -------------------------------------------------
    name = models.CharField(max_length=100)
    father_name = models.CharField(max_length=100)
    mother_name = models.CharField(max_length=100)
    dob = models.DateField(blank=True, null=True)
    guardian = models.CharField(max_length=100)
    form_b = models.CharField(max_length=50, blank=True, null=True)
    father_cnic = models.CharField(max_length=15)
    mother_cnic = models.CharField(max_length=15)
    domicile = models.CharField(max_length=50)
    religion = models.CharField(max_length=50)
    father_occupation = models.CharField(max_length=100)
    army_no = models.CharField(max_length=50, blank=True, null=True)
    rank = models.CharField(max_length=50, blank=True, null=True)

    # ← IMPORTANT: shaheed_status present (re-added)
    shaheed_status = models.CharField(
        max_length=5,
        choices=YES_NO_CHOICES,
        blank=True,
        null=True,
        verbose_name="Shaheed"
    )

    shaheed_in = models.CharField(
        max_length=50,
        choices=[
            ('in_service', 'In Service Death'),
            ('war_op', 'Death in War/Op'),
            ('accidental', 'Accidental Death'),
        ],
        blank=True,
        null=True,
        verbose_name="Shaheed In"
    )

    # make arm optional because UI hides for civilians
    arm = models.CharField(max_length=50, blank=True, null=True)
    arm_info = models.CharField(max_length=100, blank=True, null=True)
    postal_address = models.TextField()
    mobile_no = models.CharField(max_length=15)
    landline_no = models.CharField(max_length=15, blank=True, null=True)
    test_center = models.CharField(max_length=200, choices=TEST_CENTERS)

    # -------------------------------------------------
    # Academic Documents (Class XI Only)
    # -------------------------------------------------
    marksheet_9th = models.FileField(
        upload_to='xi/marksheets/9th/',
        validators=[validate_marksheet],
        null=True,
        blank=True,
        verbose_name="9th Class Marksheet"
    )
    percentage_9th = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="9th Class Percentage"
    )

    marksheet_10th = models.FileField(
        upload_to='xi/marksheets/10th/',
        validators=[validate_marksheet],
        null=True,
        blank=True,
        verbose_name="10th Class Marksheet"
    )
    percentage_10th = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="10th Class Percentage"
    )

    # -------------------------------------------------
    # Roll Number and Challan Info
    # -------------------------------------------------
    roll_number = models.CharField(max_length=20, blank=True, null=True, unique=True)
    challan_no = models.CharField(max_length=20, blank=True, null=True)
    challan_date = models.DateField(blank=True, null=True)
    secure_token = models.CharField(max_length=50, unique=True, blank=True, null=True)
    roll_slip = models.FileField(upload_to='roll_slips/', blank=True, null=True)

    # -------------------------------------------------
    # Roll Number Auto Generation
    # -------------------------------------------------
    def generate_roll_number(self):
        """
        Generates a sequential roll number based on class.
        Format: [Class]-[Sequence] (e.g., 8-0001, 11-0001)
        """
        # Determine prefix based on class
        if self.class_name == 'XI':
            prefix = '11'
        else:
            prefix = '8'  # Default to Class VIII

        # Find the highest existing sequence for this prefix
        # We filter by prefix and find the max value
        # LOCKING: Use select_for_update to prevent race conditions during bulk verify
        with transaction.atomic():
            last_app = Application.objects.filter(
                roll_number__startswith=f"{prefix}-"
            ).select_for_update().order_by('roll_number').last()

            if last_app and last_app.roll_number:
                try:
                    # Extract sequence part (e.g., "0005" from "8-0005")
                    last_seq = int(last_app.roll_number.split('-')[-1])
                    new_seq = last_seq + 1
                except ValueError:
                    # Fallback if format is unexpected
                    new_seq = 1
            else:
                new_seq = 1

        return f"{prefix}-{new_seq:04d}"

    # -------------------------------------------------
    # Save Override
    # -------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.secure_token:
            self.secure_token = uuid.uuid4().hex[:24]
        if self.status == 'verified' and not self.roll_number:
            self.roll_number = self.generate_roll_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.status})"

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['roll_number']),
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['test_center']),
        ]
        ordering = ['-submission_date']
        verbose_name = "Application"
        verbose_name_plural = "Applications"


# -------------------------------------------------
# Additional Models
# -------------------------------------------------
class FormFieldVisibility(models.Model):
    field_name = models.CharField(max_length=100, unique=True)
    is_visible = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.field_name} - {'Visible' if self.is_visible else 'Hidden'}"


class AdmissionSession(models.Model):
    CLASS_CHOICES = [
        ('VIII', 'Class VIII'),
        ('XI', 'Class XI'),
    ]
    class_name = models.CharField(max_length=10, choices=CLASS_CHOICES, unique=True)
    is_open = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_class_name_display()} ({'Open' if self.is_open else 'Closed'})"

#------------------------------------
# Fees config 
#------------------------------------
class FeeConfig(models.Model):
    CLASS_CHOICES = [
        ("VIII", "8th Class"),
        ("XI", "11th Class"),
    ]

    class_name = models.CharField(max_length=10, choices=CLASS_CHOICES, unique=True)

    # Deadlines are date fields (admin will fill them)
    normal_deadline = models.DateField(help_text="Last date for normal fee")
    late_deadline = models.DateField(help_text="Start of late/double fee (inclusive)")
    final_deadline = models.DateField(help_text="Start of final/triple fee (inclusive)")

    # If True, new applications are blocked after final_deadline
    stop_after_final = models.BooleanField(default=True)

    # Simple flat fees (useful for XI or fallback)
    base_fee = models.PositiveIntegerField(default=0, help_text="Normal fee (flat)")
    double_fee = models.PositiveIntegerField(default=0, help_text="Double fee (flat)")
    triple_fee = models.PositiveIntegerField(default=0, help_text="Triple fee (flat)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['class_name']
        verbose_name = "Fee Config"
        verbose_name_plural = "Fee Configs"

    def __str__(self):
        return f"{self.get_class_name_display()}"

class FeeCategoryConfig(models.Model):
    """
    Per-category fee rows used for class VIII (category-dependent).
    For XI you can leave this empty or not create entries.
    """
    fee_config = models.ForeignKey(FeeConfig, on_delete=models.CASCADE, related_name='category_fees')
    category = models.CharField(max_length=100, help_text="Use values from Application.CATEGORY choices")
    normal_fee = models.PositiveIntegerField(default=0)
    late_fee = models.PositiveIntegerField(default=0)
    final_fee = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('fee_config', 'category')
        ordering = ['fee_config', 'category']
        verbose_name = "Fee Category Config"
        verbose_name_plural = "Fee Category Configs"

    def __str__(self):
        return f"{self.fee_config.class_name} — {self.category}"

class MessageTemplate(models.Model):
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('verification', 'Verification'),
        ('rejection', 'Rejection'),
        ('announcement', 'Announcement'),
    ]

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='general')
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(
        help_text="Use placeholders like {name}, {roll_number}, {test_center}, {father_name}"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Message Template"
        verbose_name_plural = "Message Templates"

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"
