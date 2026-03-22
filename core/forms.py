from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User, Waiver


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'name', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to form fields
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['placeholder'] = field.label


class WaiverForm(forms.ModelForm):
    agree_to_terms = forms.BooleanField(
        required=True,
        label='I have read and agree to the waiver terms and conditions above'
    )

    class Meta:
        model = Waiver
        fields = [
            'legal_name',
            'address',
            'phone',
            'emergency_contact_name',
            'emergency_contact_relationship',
            'emergency_contact_phone',
            'id_sovereignty',
            'id_number',
            'vehicle_description',
            'vehicle_state',
            'vehicle_tag',
        ]
        labels = {
            'legal_name': 'Legal Name',
            'address': 'Address',
            'phone': 'Phone',
            'emergency_contact_name': 'Emergency Contact Name',
            'emergency_contact_relationship': 'Relationship',
            'emergency_contact_phone': 'Emergency Contact Phone',
            'id_sovereignty': 'ID State or Country',
            'id_number': 'ID Number (Driver\'s License, Govt ID, or Passport)',
            'vehicle_description': 'Vehicle Description',
            'vehicle_state': 'Vehicle State',
            'vehicle_tag': 'License Plate',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'agree_to_terms':
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'
