from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
import random
from django.contrib.auth.models import AbstractUser
from django.conf import settings



class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=15, blank=True, null=True)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    province = models.CharField(max_length=50, blank=True, null=True)
    class_applied = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.username


class EmailVerification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(default=timezone.now)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - {self.code}"

 

