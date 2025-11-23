from django import forms
from django.contrib.auth.forms import UserCreationForm
from datetime import date
from .models import User
from admissions.models import AdmissionSession  # ✅ to get open classes dynamically


# --- Step 1 Form ---
class ClassSelectionForm(forms.Form):
    class_applied = forms.ChoiceField(label="Select Class", choices=[], required=True)
    dob = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Date of Birth",
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 🧠 Fetch open classes dynamically from AdmissionSession
        open_classes = AdmissionSession.objects.filter(is_open=True).values_list('class_name', flat=True)

        if open_classes.exists():
            self.fields['class_applied'].choices = [
                (c, f"Class {c.upper()}") for c in open_classes
            ]
        else:
            self.fields['class_applied'].choices = []
            self.fields['class_applied'].widget.attrs['disabled'] = True
            self.fields['class_applied'].help_text = "⚠️ No admissions are currently open."

    def clean(self):
        # 🟢 Keep default cleaning only (no age logic here)
        cleaned_data = super().clean()
        return cleaned_data


# --- Step 2 Form ---
class StudentSignupForm(UserCreationForm):
    father_name = forms.CharField(max_length=100, required=True)
    phone = forms.CharField(max_length=15, required=True)

    class Meta:
        model = User
        fields = ['username', 'father_name', 'email', 'phone', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already registered. Please use another one.")
        return email
