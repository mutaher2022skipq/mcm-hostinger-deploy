from django import forms
from .models import Application


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = [
            # --- Personal Information ---
            'photo',
            'name',
            'father_name',
            'mother_name',
            'dob',
            'guardian',
            'form_b',
            'father_cnic',
            'mother_cnic',
            'domicile',
            'religion',
            'father_occupation',

            # --- Category & Army Info ---
            'category',
            'shaheed_status',
            'shaheed_in',
            'rank',
            'army_no',
            'arm',
            'arm_info',

            # --- Address & Contact ---
            'postal_address',
            'landline_no',
            'test_center',

            # --- Academic Info (ONLY required for Class XI) ---
            'marksheet_9th',
            'percentage_9th',
            'marksheet_10th',
            'percentage_10th',
        ]

        widgets = {
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control'}),
            'dob': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'guardian': forms.TextInput(attrs={'class': 'form-control'}),
            'form_b': forms.TextInput(attrs={'class': 'form-control'}),
            'father_cnic': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_cnic': forms.TextInput(attrs={'class': 'form-control'}),
            'domicile': forms.TextInput(attrs={'class': 'form-control'}),
            'religion': forms.TextInput(attrs={'class': 'form-control'}),
            'father_occupation': forms.TextInput(attrs={'class': 'form-control'}),

            'category': forms.Select(attrs={'class': 'form-control'}),
            'shaheed_status': forms.Select(attrs={'class': 'form-control'}),
            'shaheed_in': forms.Select(attrs={'class': 'form-control'}),

            'rank': forms.TextInput(attrs={'class': 'form-control'}),
            'army_no': forms.TextInput(attrs={'class': 'form-control'}),
            'arm': forms.TextInput(attrs={'class': 'form-control'}),
            'arm_info': forms.TextInput(attrs={'class': 'form-control'}),

            'postal_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'landline_no': forms.TextInput(attrs={'class': 'form-control'}),
            'test_center': forms.Select(attrs={'class': 'form-control'}),

            # --- Class XI Academic Fields ---
            'marksheet_9th': forms.FileInput(attrs={'class': 'form-control'}),
            'marksheet_10th': forms.FileInput(attrs={'class': 'form-control'}),
            'percentage_9th': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 100}),
            'percentage_10th': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 100}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make nonessential fields optional
        optional_fields = [
            'army_no', 'rank', 'arm', 'arm_info',
            'shaheed_status', 'shaheed_in', 'landline_no',
            'marksheet_9th', 'percentage_9th',
            'marksheet_10th', 'percentage_10th',
        ]
        for field in optional_fields:
            if field in self.fields:
                self.fields[field].required = False

    def clean(self):
        cleaned_data = super().clean()

        category = cleaned_data.get('category')
        shaheed_status = cleaned_data.get('shaheed_status')
        shaheed_in = cleaned_data.get('shaheed_in')

        # ---------------------------------------
        # CATEGORY & SHAHEED LOGIC (unchanged)
        # ---------------------------------------
        if category in ['offr_retired', 'jcos_retired']:
            if not shaheed_status:
                raise forms.ValidationError("Please specify whether Shaheed (Yes/No).")

            if shaheed_status == 'Yes' and not shaheed_in:
                raise forms.ValidationError("Please specify 'Shaheed In' details.")
        else:
            # Remove shaheed fields for categories where not required
            cleaned_data['shaheed_status'] = None
            cleaned_data['shaheed_in'] = None

        # ---------------------------------------
        # CLASS XI — Academic Eligibility Logic
        # ---------------------------------------

        # Preferred: Get class_name from Application instance
        class_name = getattr(self.instance, 'class_name', None)

        # Fallback: if instance has no class_name, get it from user.class_applied
        if not class_name and hasattr(self.instance, 'user'):
            class_name = getattr(self.instance.user, 'class_applied', None)

        if class_name == 'XI':
            perc_9 = cleaned_data.get('percentage_9th')
            sheet_9 = cleaned_data.get('marksheet_9th')

            perc_10 = cleaned_data.get('percentage_10th')
            sheet_10 = cleaned_data.get('marksheet_10th')

            # 9th Class Requirements
            if not perc_9:
                raise forms.ValidationError("9th class percentage is required for Class XI applicants.")
            if perc_9 < 60:
                raise forms.ValidationError("Minimum 60% marks in 9th class are required for Class XI.")
            if not sheet_9:
                raise forms.ValidationError("9th class marksheet upload is required.")

            # 10th Class Requirements (optional)
            if perc_10 is not None and perc_10 < 60:
                raise forms.ValidationError("Minimum 60% marks in 10th class are required for Class XI.")

        return cleaned_data

    def clean_father_cnic(self):
        cnic = self.cleaned_data.get('father_cnic')
        if cnic:
            # Remove dashes and spaces
            cleaned = cnic.replace('-', '').replace(' ', '')
            # Must be exactly 13 digits
            if not cleaned.isdigit() or len(cleaned) != 13:
                raise forms.ValidationError("CNIC must be exactly 13 digits (format: XXXXX-XXXXXXX-X).")
            # Format: XXXXX-XXXXXXX-X
            if len(cnic) == 15 and cnic.count('-') == 2:
                return cnic
            elif len(cleaned) == 13:
                # Auto-format: XXXXX-XXXXXXX-X
                return f"{cleaned[:5]}-{cleaned[5:12]}-{cleaned[12]}"
        return cnic

    def clean_mother_cnic(self):
        cnic = self.cleaned_data.get('mother_cnic')
        if cnic:
            cleaned = cnic.replace('-', '').replace(' ', '')
            if not cleaned.isdigit() or len(cleaned) != 13:
                raise forms.ValidationError("CNIC must be exactly 13 digits (format: XXXXX-XXXXXXX-X).")
            if len(cnic) == 15 and cnic.count('-') == 2:
                return cnic
            elif len(cleaned) == 13:
                return f"{cleaned[:5]}-{cleaned[5:12]}-{cleaned[12]}"
        return cnic

    def clean_mobile_no(self):
        mobile_no = self.cleaned_data.get('mobile_no')
        if mobile_no:
            # Remove spaces and dashes
            cleaned = mobile_no.replace(' ', '').replace('-', '').replace('+', '')
            # Check if it's all digits and reasonable length
            if not cleaned.isdigit():
                raise forms.ValidationError("Phone number must contain only digits.")
            if len(cleaned) < 10 or len(cleaned) > 15:
                raise forms.ValidationError("Phone number must be between 10 and 15 digits.")
        return mobile_no