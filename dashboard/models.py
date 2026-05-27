from django.conf import settings
from django.db import models


class StaffActivityLog(models.Model):
  class Action(models.TextChoices):
    PAYMENT_VERIFIED = 'payment_verified', 'Payment verified'
    PAYMENT_REJECTED = 'payment_rejected', 'Payment rejected'
    PAYMENT_RECORDED = 'payment_recorded', 'Payment recorded'
    APPOINTMENT_STATUS = 'appointment_status', 'Appointment status changed'
    APPOINTMENT_RESCHEDULED = 'appointment_rescheduled', 'Appointment rescheduled'
    SERVICE_TOGGLED = 'service_toggled', 'Service active toggled'
    TREATMENT_TOGGLED = 'treatment_toggled', 'Treatment active toggled'
    REVIEW_APPROVED = 'review_approved', 'Review approved'
    REVIEW_REJECTED = 'review_rejected', 'Review rejected'
    REVIEW_FEATURED = 'review_featured', 'Review featured'
    REVIEW_DELETED = 'review_deleted', 'Review deleted'
    CUSTOMER_NOTE_ADDED = 'customer_note_added', 'Customer note added'
    CONTACT_MESSAGE_STATUS = 'contact_message_status', 'Contact message status changed'
    CONTACT_MESSAGE_DELETED = 'contact_message_deleted', 'Contact message deleted'
    GALLERY_CREATED = 'gallery_created', 'Gallery image created'
    GALLERY_UPDATED = 'gallery_updated', 'Gallery image updated'
    GALLERY_DELETED = 'gallery_deleted', 'Gallery image deleted'
    ANNOUNCEMENT_CREATED = 'announcement_created', 'Announcement created'
    ANNOUNCEMENT_UPDATED = 'announcement_updated', 'Announcement updated'
    ANNOUNCEMENT_DELETED = 'announcement_deleted', 'Announcement deleted'

  user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
    related_name='staff_activity_logs',
  )
  action = models.CharField(max_length=40, choices=Action.choices)
  target_type = models.CharField(max_length=40, blank=True)
  target_id = models.CharField(max_length=64, blank=True)
  message = models.CharField(max_length=500)
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['-created_at']
    indexes = [
      models.Index(fields=['-created_at']),
      models.Index(fields=['action']),
    ]

  def __str__(self):
    return self.message
