from django.contrib.auth import get_user_model
from admissions.models import Application
from datetime import datetime, timedelta
import random

User = get_user_model()

def run():
    categories = [
        'offr_serving', 'offr_retired',
        'jcos_serving', 'civilian'
    ]
    centers = ['rawalpindi', 'lahore', 'quetta']
    statuses = ['pending', 'under_review', 'verified']

    total = 2000  # number of dummy applicants

    print("Creating users...")

    users_to_create = []
    apps_to_create = []

    for i in range(total):
        username = f"dummy_{i}"
        email = f"dummy_{i}@example.com"

        users_to_create.append(
            User(
                username=username,
                email=email,
                first_name=f"Dummy {i}"
            )
        )

    # Bulk create users (ignore duplicates)
    User.objects.bulk_create(users_to_create, ignore_conflicts=True)

    print("Users created.")
    print("Fetching users...")

    users = User.objects.filter(username__startswith="dummy_").order_by("id")

    print("Creating applications...")

    for idx, user in enumerate(users):
        apps_to_create.append(
            Application(
                user=user,
                name=f"Dummy Applicant {idx}",
                father_name=f"Dummy Father {idx}",
                category=random.choice(categories),
                payment_status=random.choice(statuses),
                status=random.choice(statuses),
                test_center=random.choice(centers),
                submission_date=datetime.now() - timedelta(days=random.randint(1, 15)),
            )
        )

    Application.objects.bulk_create(apps_to_create)

    print("DONE — 2000 dummy applicants created successfully.")
