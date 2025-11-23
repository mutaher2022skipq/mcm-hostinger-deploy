from django.urls import path
from . import views

app_name = 'admissions'

urlpatterns = [
    # 🧭 Student dashboard and application
    path('dashboard/', views.dashboard, name='dashboard'),
    path('complete-form/', views.complete_application, name='complete_form'),
    path('view-application/', views.view_application, name='view_application'),

    # 💰 Challan related
    path('print-challan/', views.print_challan, name='print_challan'),
    path('challan-pdf/', views.challan_pdf, name='challan_pdf'),
    path('upload-fee-slip/', views.upload_fee_slip, name='upload_fee_slip'),

    # 🧾 Admin: challan verification and actions
    path('verify-fees/', views.verify_challan_list, name='verify_challans'),
    path('verify-fees/<int:app_id>/<str:action>/', views.verify_challan_action, name='verify_challan_action'),
    path('challan-details/<int:app_id>/', views.challan_details, name='challan_details'),

    # 🎫 Roll Number Slip (dashboard + email link)
    path('dashboard/download-roll-slip/', views.download_roll_slip_dashboard, name='download_roll_slip_dashboard'),
    path('download-roll-slip/<str:token>/', views.download_roll_slip, name='download_roll_slip'),

    # 🛠️ Admin: dashboards and management
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/applicant/<int:app_id>/', views.view_applicant, name='view_applicant'),
    path('toggle-admission/<int:session_id>/', views.toggle_admission, name='toggle_admission'),
    path('form-field-control/', views.form_field_control, name='form_field_control'),
    path('view-fee-slip/<int:app_id>/', views.view_fee_slip, name='view_fee_slip'),
    # API for admin listing + filters (AJAX)
    path('admin-api/applicants/', views.admin_applicants_api, name='admin_applicants_api'),
    # Bulk actions (verify, reject, assign_center)
    path('admin-api/applicants/bulk-action/', views.bulk_applicant_action, name='bulk_applicant_action'),
    path('analytics-data/', views.analytics_data, name='analytics_data'),
    path('admin-analytics/', views.admin_analytics, name='admin_analytics'),
        # ✅ Add this missing route
    path('export-analytics-pdf/', views.export_analytics_pdf, name='export_analytics_pdf'),
    path('export-csv/', views.export_applicants_csv, name='export_applicants_csv'),
    path('export-excel/', views.export_applicants_excel, name='export_applicants_excel'),
    path('broadcast-messages/', views.broadcast_messages, name='broadcast_messages'),
    path('broadcast-preview/', views.broadcast_preview, name='broadcast_preview'),
    path('create-template/', views.create_message_template, name='create_message_template'),
    
    path('admin/fees/', views.fee_management_dashboard, name='fee_management'),
    path('admin/fees/<int:pk>/edit/', views.fee_config_edit, name='fee_config_edit'),
    path('admin/fees/<int:pk>/categories/<int:cat_pk>/edit/', views.fee_category_edit, name='fee_category_edit'),
    path('admin/fees/preview/', views.fee_preview_ajax, name='fee_preview_ajax'),


]
