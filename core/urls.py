from django.urls import path
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('survival-guide/', views.survival_guide, name='survival_guide'),
    path('10-principles/', views.principles, name='principles'),

    # Authentication
    path('login/', LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),

    # Password reset
    path('password-reset/',
         PasswordResetView.as_view(template_name='core/password_reset.html'),
         name='password_reset'),
    path('password-reset/done/',
         PasswordResetDoneView.as_view(template_name='core/password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         PasswordResetConfirmView.as_view(template_name='core/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         PasswordResetCompleteView.as_view(template_name='core/password_reset_complete.html'),
         name='password_reset_complete'),

    # Tickets
    path('tickets/', views.tickets, name='tickets'),
    path('checkout/create-session/', views.create_checkout_session, name='create_checkout_session'),
    path('checkout/success/', views.checkout_success, name='checkout_success'),
    path('checkout/cancel/', views.checkout_cancel, name='checkout_cancel'),

    # Ticket management
    path('my-tickets/', views.my_tickets, name='my_tickets'),
    path('my-tickets/transfer/<int:order_id>/', views.transfer_ticket, name='transfer_ticket'),
    path('my-tickets/accept/<int:transfer_id>/', views.accept_transfer, name='accept_transfer'),
    path('my-tickets/reject/<int:transfer_id>/', views.reject_transfer, name='reject_transfer'),
    path('my-tickets/rescind/<int:transfer_id>/', views.rescind_transfer, name='rescind_transfer'),

    # Shifts
    path('shifts/', views.shifts, name='shifts'),
    path('shifts/signup/<int:shift_id>/', views.shift_signup, name='shift_signup'),
    path('shifts/cancel/<int:shift_id>/', views.shift_cancel, name='shift_cancel'),
]
