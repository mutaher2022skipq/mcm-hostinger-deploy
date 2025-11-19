from .models import Notification

def send_notification(user, title, message, link=None):
    """Helper to create a notification."""
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link
    )
