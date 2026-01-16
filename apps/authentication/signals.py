"""
Signals for authentication app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create a UserProfile automatically when a User is created.
    """
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                'timezone': 'UTC',
                'language': 'en',
                'email_notifications': True,
                'sms_notifications': False,
                'push_notifications': True,
                'skills': [],
                'certifications': [],
            }
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Ensure profile exists when user is saved.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        # Create profile if it doesn't exist
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                'timezone': 'UTC',
                'language': 'en',
                'email_notifications': True,
                'sms_notifications': False,
                'push_notifications': True,
                'skills': [],
                'certifications': [],
            }
        )
