import base64
import io
import json
from urllib.parse import quote

import qrcode
import stripe
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.db.models import Count

from .forms import CustomUserCreationForm, WaiverForm
from .models import Event, Order, Transfer, User, Role, Shift, ShiftAssignment, Waiver

stripe.api_key = settings.STRIPE_SECRET_KEY


def home(request):
    return render(request, 'core/index.html')


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'core/register.html', {'form': form})


def survival_guide(request):
    return render(request, 'core/survival_guide.html')


def principles(request):
    return render(request, 'core/principles.html')


@login_required
def tickets(request):
    """Display ticket selection page."""
    event = Event.get_active()
    if not event:
        messages.error(request, 'No active event. Ticket sales are currently closed.')
        return redirect('home')

    existing_counts = dict(
        Order.objects.filter(
            ticket_type__event=event,
            owning_user=request.user,
            status__in=['completed', 'pending'],
        ).values_list('ticket_type_id').annotate(count=Count('id'))
    )
    ticket_data = []
    for ticket_type in event.ticket_types.all():
        existing = existing_counts.get(ticket_type.id, 0)
        ticket_data.append({
            'ticket_type': ticket_type,
            'remaining': max(0, ticket_type.max_per_user - existing),
        })
    return render(request, 'core/tickets.html', {
        'event': event,
        'ticket_data': ticket_data,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    })


@login_required
@require_POST
def create_payment_intent(request):
    """Create a Stripe PaymentIntent and render the custom checkout page."""
    event = Event.get_active()
    if not event:
        messages.error(request, 'No active event. Ticket sales are currently closed.')
        return redirect('home')

    tickets_to_create = []
    total_cents = 0

    for ticket_type in event.ticket_types.all():
        quantity = int(request.POST.get(f'quantity_{ticket_type.id}', 0))
        if quantity > 0:
            for _ in range(quantity):
                tickets_to_create.append(ticket_type)
            total_cents += quantity * ticket_type.price

    if not tickets_to_create:
        messages.error(request, 'Please select at least one ticket.')
        return redirect('tickets')

    # Check ticket limits per user for this event
    existing_counts = dict(
        Order.objects.filter(
            ticket_type__event=event,
            owning_user=request.user,
            status__in=['completed', 'pending'],
        ).values('ticket_type_id').annotate(count=Count('id')).values_list('ticket_type_id', 'count')
    )

    requested_counts = {}
    for ticket_type in tickets_to_create:
        requested_counts[ticket_type.id] = requested_counts.get(ticket_type.id, 0) + 1

    for ticket_type in event.ticket_types.all():
        existing = existing_counts.get(ticket_type.id, 0)
        requested = requested_counts.get(ticket_type.id, 0)
        if existing + requested > ticket_type.max_per_user:
            remaining = max(0, ticket_type.max_per_user - existing)
            messages.error(
                request,
                f'You can only have {ticket_type.max_per_user} {ticket_type.label.lower()}s. '
                f'You already have {existing}, so you can only purchase {remaining} more.'
            )
            return redirect('tickets')

    # Create Stripe PaymentIntent
    payment_intent = stripe.PaymentIntent.create(
        amount=total_cents,
        currency='usd',
        automatic_payment_methods={'enabled': True},
        metadata={
            'user_id': request.user.id,
        },
    )

    # Create pending orders (one per ticket)
    for ticket_type in tickets_to_create:
        Order.objects.create(
            ticket_type=ticket_type,
            purchasing_user=request.user,
            owning_user=request.user,
            stripe_payment_intent_id=payment_intent.id,
            status='pending',
        )

    # Build order summary for template
    order_summary = []
    for ticket_type_id, count in requested_counts.items():
        ticket_type = next(tt for tt in event.ticket_types.all() if tt.id == ticket_type_id)
        subtotal = (ticket_type.price * count) / 100
        order_summary.append({
            'label': ticket_type.label,
            'quantity': count,
            'subtotal': f'{subtotal:.2f}',
        })

    # Build absolute URLs for Stripe
    success_url = request.build_absolute_uri(f'/checkout/success/?payment_intent={payment_intent.id}')

    # Check if user needs to sign waiver
    has_waiver = Waiver.objects.filter(user=request.user, event=event).exists()
    waiver_form = None
    if not has_waiver:
        waiver_form = WaiverForm(initial={'legal_name': request.user.name})

    return render(request, 'core/checkout.html', {
        'client_secret': payment_intent.client_secret,
        'payment_intent_id': payment_intent.id,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
        'order_summary': order_summary,
        'total_display': f'{total_cents / 100:.2f}',
        'success_url': success_url,
        'waiver_form': waiver_form,
        'event': event,
    })


@login_required
@require_POST
def confirm_payment(request):
    """Handle payment confirmation callback from frontend."""
    try:
        data = json.loads(request.body)
        payment_intent_id = data.get('payment_intent_id')
        waiver_data = data.get('waiver_data')

        if not payment_intent_id:
            return JsonResponse({'success': False, 'error': 'Missing payment intent ID'}, status=400)

        # Verify PaymentIntent status with Stripe
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        if payment_intent.status == 'succeeded':
            # Update orders to completed
            Order.objects.filter(
                stripe_payment_intent_id=payment_intent_id,
                purchasing_user=request.user,
                status='pending',
            ).update(status='completed')

            # Save waiver if provided and user hasn't signed yet
            if waiver_data:
                event = Event.get_active()
                if event and not Waiver.objects.filter(user=request.user, event=event).exists():
                    waiver_form = WaiverForm(waiver_data)
                    if waiver_form.is_valid():
                        waiver_obj = waiver_form.save(commit=False)
                        waiver_obj.user = request.user
                        waiver_obj.event = event
                        waiver_obj.save()

            return JsonResponse({'success': True})
        else:
            return JsonResponse({
                'success': False,
                'error': f'Payment not completed. Status: {payment_intent.status}'
            })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except stripe.error.StripeError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def checkout_success(request):
    """Handle successful checkout."""
    payment_intent_id = request.GET.get('payment_intent')
    if payment_intent_id:
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            if payment_intent.status == 'succeeded':
                Order.objects.filter(
                    stripe_payment_intent_id=payment_intent_id,
                    purchasing_user=request.user,
                    status='pending',
                ).update(status='completed')
        except Exception:
            pass

    return render(request, 'core/checkout_success.html')


@login_required
def checkout_cancel(request):
    """Handle cancelled checkout and clean up pending orders."""
    payment_intent_id = request.GET.get('payment_intent_id')
    if payment_intent_id:
        # Cancel pending orders for this payment intent
        Order.objects.filter(
            stripe_payment_intent_id=payment_intent_id,
            purchasing_user=request.user,
            status='pending',
        ).update(status='cancelled')

        # Cancel the PaymentIntent with Stripe
        try:
            stripe.PaymentIntent.cancel(payment_intent_id)
        except stripe.error.StripeError:
            pass  # PaymentIntent may already be cancelled or in a non-cancellable state

    return render(request, 'core/checkout_cancel.html')


@login_required
def my_tickets(request):
    """Display user's tickets and pending transfers."""
    event = Event.get_active()

    owned_tickets = Order.objects.filter(
        ticket_type__event=event,
        owning_user=request.user,
        status='completed',
    ).select_related('ticket_type', 'purchasing_user') if event else Order.objects.none()

    outgoing_transfers = Transfer.objects.filter(
        order__ticket_type__event=event,
        from_user=request.user,
        status='pending',
    ).select_related('order__ticket_type') if event else Transfer.objects.none()

    incoming_transfers = Transfer.objects.filter(
        order__ticket_type__event=event,
        to_email=request.user.email,
        status='pending',
    ).select_related('order__ticket_type', 'from_user') if event else Transfer.objects.none()

    # Generate QR code only if user has tickets
    qr_code_data_url = None
    if owned_tickets.exists():
        qr = qrcode.make(request.build_absolute_uri('/checkin?email=' + quote(request.user.email)))
        buffer = io.BytesIO()
        qr.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        qr_code_data_url = f"data:image/png;base64,{qr_base64}"

    return render(request, 'core/my_tickets.html', {
        'event': event,
        'owned_tickets': owned_tickets,
        'outgoing_transfers': outgoing_transfers,
        'incoming_transfers': incoming_transfers,
        'qr_code_data_url': qr_code_data_url,
    })


@login_required
@require_POST
def transfer_ticket(request, order_id):
    """Initiate a ticket transfer."""
    order = get_object_or_404(Order, id=order_id, owning_user=request.user, status='completed')

    # Check if there's already a pending transfer for this order
    if Transfer.objects.filter(order=order, status='pending').exists():
        messages.error(request, 'This ticket already has a pending transfer.')
        return redirect('my_tickets')

    to_email = request.POST.get('to_email', '').strip().lower()
    if not to_email:
        messages.error(request, 'Please enter an email address.')
        return redirect('my_tickets')

    if to_email == request.user.email:
        messages.error(request, 'You cannot transfer a ticket to yourself.')
        return redirect('my_tickets')

    # Check if recipient exists
    to_user = User.objects.filter(email=to_email).first()
    if not to_user:
        messages.error(request, 'No user found with that email address.')
        return redirect('my_tickets')

    # Check recipient's ticket limits for this event
    existing_count = Order.objects.filter(
        ticket_type=order.ticket_type,
        owning_user=to_user,
        status__in=['completed', 'pending'],
    ).count()
    pending_transfers = Transfer.objects.filter(
        to_email=to_email,
        order__ticket_type=order.ticket_type,
        status='pending',
    ).count()
    if existing_count + pending_transfers >= order.ticket_type.max_per_user:
        messages.error(request, 'The recipient has reached their limit for this ticket type.')
        return redirect('my_tickets')

    Transfer.objects.create(
        order=order,
        from_user=request.user,
        to_email=to_email,
        to_user=to_user,
    )

    messages.success(request, f'Transfer initiated to {to_email}.')
    return redirect('my_tickets')


@login_required
def accept_transfer(request, transfer_id):
    """Accept an incoming transfer, with waiver form if needed."""
    transfer = get_object_or_404(
        Transfer,
        id=transfer_id,
        to_email=request.user.email,
        status='pending',
    )

    event = Event.get_active()
    if not event:
        messages.error(request, 'No active event.')
        return redirect('my_tickets')

    # Check ticket limits for this event
    existing_count = Order.objects.filter(
        ticket_type=transfer.order.ticket_type,
        owning_user=request.user,
        status__in=['completed', 'pending'],
    ).count()
    if existing_count >= transfer.order.ticket_type.max_per_user:
        messages.error(request, 'You have reached your limit for this ticket type.')
        return redirect('my_tickets')

    # Check if user needs to sign waiver
    has_waiver = Waiver.objects.filter(user=request.user, event=event).exists()

    if request.method == 'POST':
        # Process waiver form if user hasn't signed yet
        if not has_waiver:
            waiver_form = WaiverForm(request.POST)
            if not waiver_form.is_valid():
                return render(request, 'core/accept_transfer.html', {
                    'transfer': transfer,
                    'waiver_form': waiver_form,
                    'event': event,
                })
            # Save the waiver
            waiver_obj = waiver_form.save(commit=False)
            waiver_obj.user = request.user
            waiver_obj.event = event
            waiver_obj.save()

        # Complete the transfer
        transfer.order.owning_user = request.user
        transfer.order.save()

        transfer.to_user = request.user
        transfer.status = 'accepted'
        transfer.save()

        messages.success(request, 'Transfer accepted. The ticket is now yours.')
        return redirect('my_tickets')

    # GET request - show the accept page
    waiver_form = None
    if not has_waiver:
        waiver_form = WaiverForm(initial={'legal_name': request.user.name})

    return render(request, 'core/accept_transfer.html', {
        'transfer': transfer,
        'waiver_form': waiver_form,
        'event': event,
    })


@login_required
@require_POST
def reject_transfer(request, transfer_id):
    """Reject an incoming transfer."""
    transfer = get_object_or_404(
        Transfer,
        id=transfer_id,
        to_email=request.user.email,
        status='pending',
    )

    transfer.status = 'rejected'
    transfer.save()

    messages.success(request, 'Transfer rejected.')
    return redirect('my_tickets')


@login_required
@require_POST
def rescind_transfer(request, transfer_id):
    """Rescind an outgoing transfer."""
    transfer = get_object_or_404(
        Transfer,
        id=transfer_id,
        from_user=request.user,
        status='pending',
    )

    transfer.delete()

    messages.success(request, 'Transfer rescinded.')
    return redirect('my_tickets')


@login_required
def shifts(request):
    """Display shift signup page with a table of roles and hours."""
    from datetime import timedelta

    event = Event.get_active()
    if not event:
        messages.error(request, 'No active event.')
        return redirect('home')

    roles = Role.objects.filter(event=event).prefetch_related(
        'shifts__assignments__user'
    )

    # Check if user has a ticket for this event
    has_ticket = Order.objects.filter(
        ticket_type__event=event,
        owning_user=request.user,
        status='completed',
    ).exists()

    # Count user's current shifts for this event
    user_shift_count = ShiftAssignment.objects.filter(
        user=request.user,
        shift__role__event=event
    ).count()
    can_signup_more = event.max_shifts_per_user == 0 or user_shift_count < event.max_shifts_per_user

    if not roles.exists():
        return render(request, 'core/shifts.html', {
            'event': event,
            'roles': [],
            'grid': [],
            'hours': [],
            'has_ticket': has_ticket,
            'user_shift_count': user_shift_count,
            'can_signup_more': can_signup_more,
        })

    # Collect all shifts and find time boundaries
    all_shifts = Shift.objects.filter(role__event=event).select_related('role').prefetch_related('assignments__user')

    if not all_shifts.exists():
        return render(request, 'core/shifts.html', {
            'event': event,
            'roles': roles,
            'grid': [],
            'hours': [],
            'has_ticket': has_ticket,
            'user_shift_count': user_shift_count,
            'can_signup_more': can_signup_more,
        })

    min_time = min(s.start_time for s in all_shifts)
    max_time = max(s.end_time for s in all_shifts)

    # Round to hour boundaries
    min_hour = min_time.replace(minute=0, second=0, microsecond=0)
    max_hour = max_time.replace(minute=0, second=0, microsecond=0)
    if max_time > max_hour:
        max_hour += timedelta(hours=1)

    # Build list of hours
    hours = []
    current = min_hour
    while current < max_hour:
        hours.append(current)
        current += timedelta(hours=1)

    # Build a mapping of (role_id, hour) -> shift for quick lookup
    # A shift covers all hours from start to end
    role_hour_shift = {}
    for shift in all_shifts:
        shift_start_hour = shift.start_time.replace(minute=0, second=0, microsecond=0)
        shift_end_hour = shift.end_time.replace(minute=0, second=0, microsecond=0)
        if shift.end_time > shift_end_hour:
            shift_end_hour += timedelta(hours=1)

        current = shift_start_hour
        while current < shift_end_hour:
            role_hour_shift[(shift.role_id, current)] = shift
            current += timedelta(hours=1)

    # Get user's current assignments
    user_assignments = set(
        ShiftAssignment.objects.filter(
            user=request.user,
            shift__role__event=event
        ).values_list('shift_id', flat=True)
    )

    # Build the grid
    # Each row is an hour, each cell is either:
    # - {'type': 'empty'} - no shift
    # - {'type': 'shift_start', 'shift': shift, 'rowspan': N, 'is_signed_up': bool} - start of a shift
    # - {'type': 'shift_continue'} - continuation (skip rendering)
    grid = []
    for hour in hours:
        row = {'hour': hour, 'cells': []}
        for role in roles:
            shift = role_hour_shift.get((role.id, hour))
            if shift is None:
                row['cells'].append({'type': 'empty'})
            else:
                # Check if this is the start hour of the shift
                shift_start_hour = shift.start_time.replace(minute=0, second=0, microsecond=0)
                if hour == shift_start_hour:
                    # Calculate rowspan (number of hours)
                    shift_end_hour = shift.end_time.replace(minute=0, second=0, microsecond=0)
                    if shift.end_time > shift_end_hour:
                        shift_end_hour += timedelta(hours=1)
                    rowspan = int((shift_end_hour - shift_start_hour).total_seconds() // 3600)

                    row['cells'].append({
                        'type': 'shift_start',
                        'shift': shift,
                        'rowspan': rowspan,
                        'is_signed_up': shift.id in user_assignments,
                    })
                else:
                    row['cells'].append({'type': 'shift_continue'})
        grid.append(row)

    return render(request, 'core/shifts.html', {
        'event': event,
        'roles': roles,
        'grid': grid,
        'hours': hours,
        'has_ticket': has_ticket,
        'user_shift_count': user_shift_count,
        'can_signup_more': can_signup_more,
    })


@login_required
@require_POST
def shift_signup(request, shift_id):
    """Sign up for a shift."""
    event = Event.get_active()
    if not event:
        messages.error(request, 'No active event.')
        return redirect('home')

    # Check if user has a ticket for this event
    has_ticket = Order.objects.filter(
        ticket_type__event=event,
        owning_user=request.user,
        status='completed',
    ).exists()
    if not has_ticket:
        messages.error(request, 'You must have a ticket to sign up for shifts.')
        return redirect('shifts')

    # Check shift limit
    if event.max_shifts_per_user > 0:
        user_shift_count = ShiftAssignment.objects.filter(
            user=request.user,
            shift__role__event=event
        ).count()
        if user_shift_count >= event.max_shifts_per_user:
            messages.error(request, f'You have reached the maximum of {event.max_shifts_per_user} shifts.')
            return redirect('shifts')

    shift = get_object_or_404(Shift, id=shift_id, role__event=event)

    # Check if already signed up
    if ShiftAssignment.objects.filter(shift=shift, user=request.user).exists():
        messages.error(request, 'You are already signed up for this shift.')
        return redirect('shifts')

    # Check capacity
    if shift.spots_remaining <= 0:
        messages.error(request, 'This shift is full.')
        return redirect('shifts')

    ShiftAssignment.objects.create(shift=shift, user=request.user)
    messages.success(request, f'You have signed up for {shift}.')
    return redirect('shifts')


@login_required
@require_POST
def shift_cancel(request, shift_id):
    """Cancel shift signup."""
    event = Event.get_active()
    if not event:
        messages.error(request, 'No active event.')
        return redirect('home')

    shift = get_object_or_404(Shift, id=shift_id, role__event=event)

    assignment = ShiftAssignment.objects.filter(shift=shift, user=request.user).first()
    if not assignment:
        messages.error(request, 'You are not signed up for this shift.')
        return redirect('shifts')

    assignment.delete()
    messages.success(request, f'You have cancelled your signup for {shift}.')
    return redirect('shifts')


@login_required
def checkin(request):
    """Check-in page for superusers to look up attendees by email."""
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('home')

    email = request.GET.get('email', '').strip().lower()
    if email:
        user = User.objects.filter(email=email).first()
        if user:
            return redirect('checkin_user', email=email)
        else:
            messages.error(request, 'No user found with that email address.')

    return render(request, 'core/checkin.html')


@login_required
def checkin_user(request, email):
    """Display check-in details for a specific user."""
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('home')

    user = get_object_or_404(User, email=email.lower())
    event = Event.get_active()

    base_tickets = Order.objects.filter(
        ticket_type__event=event,
        owning_user=user,
        status='completed',
    ).select_related('ticket_type') if event else Order.objects.none()

    unclaimed_tickets = base_tickets.filter(claimed_at__isnull=True)
    claimed_tickets = base_tickets.filter(claimed_at__isnull=False)

    has_waiver = Waiver.objects.filter(user=user, event=event).exists() if event else False

    return render(request, 'core/checkin_user.html', {
        'checkin_user': user,
        'event': event,
        'unclaimed_tickets': unclaimed_tickets,
        'claimed_tickets': claimed_tickets,
        'has_waiver': has_waiver,
    })


@login_required
@require_POST
def claim_tickets(request, email):
    """Claim selected tickets for a user."""
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('home')

    user = get_object_or_404(User, email=email.lower())
    ticket_ids = request.POST.getlist('ticket_ids')

    if not ticket_ids:
        messages.error(request, 'No tickets selected.')
        return redirect('checkin_user', email=email)

    event = Event.get_active()

    # Check waiver requirement
    has_waiver = Waiver.objects.filter(user=user, event=event).exists() if event else False
    waiver_signed = request.POST.get('waiver_signed') == 'on'

    if not has_waiver and not waiver_signed:
        messages.error(request, 'Cannot check in without a signed waiver. Either have the user complete the waiver online or check the box confirming the waiver was signed.')
        return redirect('checkin_user', email=email)
    updated = Order.objects.filter(
        id__in=ticket_ids,
        ticket_type__event=event,
        owning_user=user,
        status='completed',
        claimed_at__isnull=True,
    ).update(claimed_at=timezone.now())

    if updated:
        messages.success(request, f'{updated} ticket(s) claimed successfully.')
    else:
        messages.error(request, 'No tickets were claimed.')

    return redirect('checkin_user', email=email)
