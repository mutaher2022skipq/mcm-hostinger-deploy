import os
import django
import random
import uuid
from django.utils import timezone

# 1. Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mcm_admission.settings')
django.setup()

# 2. Import Models (Must be after setup)
from django.contrib.auth import get_user_model
from admissions.models import Application

User = get_user_model()

def create_dummy_data():
    print("Creating 2000 dummy applications...")
    
    users = []
    applications = []
    
    # Prefetch existing usernames to avoid collision
    existing_usernames = set(User.objects.values_list('username', flat=True))

    # Optimization: Hash password ONCE to avoid 2000x CPU calculation
    from django.contrib.auth.hashers import make_password
    password_hash = make_password("password123")

    for i in range(2000):
        username = f"dummy_user_{i}"
        if username in existing_usernames:
            continue
            
        # Create User
        user = User(username=username, email=f"{username}@example.com")
        user.password = password_hash  # Assign pre-calculated hash
        users.append(user)

    # Bulk create users
    User.objects.bulk_create(users)
    print(f"Created {len(users)} users.")
    
    # Fetch created users to get IDs
    created_users = User.objects.filter(username__startswith="dummy_user_")
    
    for user in created_users:
        app = Application(
            user=user,
            name=f"Student {user.username}",
            father_name=f"Father {user.username}",
            mother_name="Mother Name",
            guardian="Guardian Name",
            father_cnic="12345-1234567-1",
            mother_cnic="12345-1234567-2",
            mobile_no="0300-1234567",
            postal_address="Dummy Address 123",
            test_center=random.choice([c[0] for c in Application.TEST_CENTERS]),
            category=random.choice([c[0] for c in Application.CATEGORY_CHOICES]),
            status=random.choice(['submitted', 'verified', 'payment_pending']),
            payment_status=random.choice(['verified', 'pending']),
            class_name=random.choice(['VIII', 'XI']),
            submission_date=timezone.now(),
            domicile="Punjab",
            religion="Islam",
            father_occupation="Soldier",
            secure_token=uuid.uuid4().hex[:24]
        )
        applications.append(app)

    # Bulk create applications
    Application.objects.bulk_create(applications)
    print(f"Successfully created {len(applications)} dummy applications.")

def delete_dummy_data():
    print("Deleting dummy data...")
    count, _ = User.objects.filter(username__startswith="dummy_user_").delete()
    print(f"Deleted {count} dummy records.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--delete':
        delete_dummy_data()
    else:
        create_dummy_data()
