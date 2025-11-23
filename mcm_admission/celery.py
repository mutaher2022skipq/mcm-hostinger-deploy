import os
from celery import Celery

# Default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mcm_admission.settings')

app = Celery('mcm_admission')

# Load configuration from Django settings using CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
