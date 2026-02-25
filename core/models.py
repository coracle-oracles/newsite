from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']


class Event(models.Model):
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    max_shifts_per_user = models.PositiveIntegerField(default=0, help_text='Maximum shifts per user (0 = unlimited)')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_active:
            Event.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        return cls.objects.filter(is_active=True).first()


class TicketType(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_types')
    name = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.PositiveIntegerField(help_text='Price in cents')
    stripe_price_id = models.CharField(max_length=255)
    max_per_user = models.PositiveIntegerField(default=4)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = [['event', 'name']]

    def __str__(self):
        return f"{self.label} ({self.event.name})"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    ticket_type = models.ForeignKey(TicketType, on_delete=models.RESTRICT, related_name='orders')
    purchasing_user = models.ForeignKey('User', on_delete=models.RESTRICT, related_name='purchased_orders')
    owning_user = models.ForeignKey('User', on_delete=models.RESTRICT, related_name='owned_orders')

    stripe_checkout_session_id = models.CharField(max_length=255)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.id} - {self.owning_user.email} - {self.ticket_type.label}"


class Transfer(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='transfers')
    from_user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='outgoing_transfers')
    to_email = models.EmailField()
    to_user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='incoming_transfers', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Transfer {self.id} - {self.order} -> {self.to_email}"


class Role(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    leads = models.ManyToManyField('User', related_name='led_roles', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = [['event', 'name']]

    def __str__(self):
        return f"{self.name} ({self.event.name})"


class Shift(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='shifts')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    capacity = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_time']
        unique_together = [['role', 'start_time', 'end_time']]

    def __str__(self):
        return f"{self.role.name} - {self.start_time.strftime('%b %d, %I:%M %p')} to {self.end_time.strftime('%I:%M %p')}"

    @property
    def spots_remaining(self):
        return self.capacity - self.assignments.count()


class ShiftAssignment(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='assignments')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='shift_assignments')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['shift', 'user']]
        ordering = ['shift__start_time']

    def __str__(self):
        return f"{self.user.email} - {self.shift}"
