from django.contrib.auth import get_user_model
from admissions.models import Application

User = get_user_model()

def run():
    print("Deleting dummy records...")

    apps = Application.objects.filter(user__username__startswith="dummy_")
    users = User.objects.filter(username__startswith="dummy_")

    app_count = apps.count()
    user_count = users.count()

    apps.delete()
    users.delete()

    print(f"Deleted {app_count} dummy applications.")
    print(f"Deleted {user_count} dummy users.")
