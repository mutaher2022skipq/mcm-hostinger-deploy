from django.contrib import admin
from django.utils.html import format_html
from .models import Application, AdmissionSession, MessageTemplate  # ✅ Added MessageTemplate import
from django.contrib import admin
from .models import FeeConfig, FeeCategoryConfig


# -------------------------------------------------
# Application Admin
# -------------------------------------------------
@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'father_name',
        'category',
        'amount',
        'challan_no',
        'payment_status',
        'challan_preview',
        'submission_date',
    )
    search_fields = ('name', 'father_name', 'form_b', 'challan_no')
    list_filter = ('payment_status', 'category', 'status')
    readonly_fields = ('challan_preview',)
    actions = ['verify_payment', 'reject_payment']

    def challan_preview(self, obj):
        """Show challan image thumbnail in admin."""
        if obj.challan_image:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover; border-radius: 5px;" />',
                obj.challan_image.url
            )
        return "No challan uploaded"
    challan_preview.short_description = "Challan Image"

    def verify_payment(self, request, queryset):
        """Admin action to verify selected payments."""
        updated = queryset.update(payment_status='verified', admin_remarks='Payment verified.')
        self.message_user(request, f"{updated} challan(s) verified successfully ✅")

    def reject_payment(self, request, queryset):
        """Admin action to reject selected payments."""
        updated = queryset.update(payment_status='rejected', admin_remarks='Invalid or unclear challan image.')
        self.message_user(request, f"{updated} challan(s) rejected ❌")

    verify_payment.short_description = "Mark as Payment Verified"
    reject_payment.short_description = "Mark as Payment Rejected"


#-------------------------------------
# Fees setting
#--------------------------------------
class FeeCategoryInline(admin.TabularInline):
    model = FeeCategoryConfig
    extra = 0

@admin.register(FeeConfig)
class FeeConfigAdmin(admin.ModelAdmin):
    list_display = ('class_name', 'normal_deadline', 'late_deadline', 'final_deadline', 'stop_after_final')
    inlines = [FeeCategoryInline]
    search_fields = ('class_name',)
    list_filter = ('class_name',)

@admin.register(FeeCategoryConfig)
class FeeCategoryConfigAdmin(admin.ModelAdmin):
    list_display = ('fee_config', 'category', 'normal_fee', 'late_fee', 'final_fee')
    search_fields = ('category',)
    list_filter = ('fee_config',)

# -------------------------------------------------
# Admission Session Admin
# -------------------------------------------------
@admin.register(AdmissionSession)
class AdmissionSessionAdmin(admin.ModelAdmin):
    list_display = ('class_name', 'is_open')
    list_editable = ('is_open',)


# -------------------------------------------------
# 🌿 Message Template Admin (Phase 4)
# -------------------------------------------------
@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_by', 'created_at')
    search_fields = ('title', 'category', 'body')
    list_filter = ('category', 'created_at')
    ordering = ('-created_at',)
