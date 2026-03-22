import logging
from datetime import timedelta

import stripe
from django.conf import settings
from django.tasks import task
from django.utils import timezone

from .models import Order

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

RECONCILIATION_INTERVAL_MINUTES = 10


@task
def reconcile_pending_orders(max_age_minutes=60):
    """
    Reconcile pending orders by checking their PaymentIntent status with Stripe.

    Finds orders that are still pending after a grace period and verifies
    their payment status directly with Stripe's API.

    This task reschedules itself to run every 10 minutes.
    """
    cutoff = timezone.now() - timedelta(minutes=5)
    max_age = timezone.now() - timedelta(minutes=max_age_minutes)

    pending_intents = Order.objects.filter(
        status='pending',
        stripe_payment_intent_id__isnull=False,
        created_at__lt=cutoff,
        created_at__gt=max_age,
    ).values_list('stripe_payment_intent_id', flat=True).distinct()

    reconciled = 0
    for payment_intent_id in pending_intents:
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if payment_intent.status == 'succeeded':
                updated = Order.objects.filter(
                    stripe_payment_intent_id=payment_intent_id,
                    status='pending',
                ).update(status='completed')
                reconciled += updated
                logger.info(f"Reconciled PaymentIntent {payment_intent_id} - marked {updated} orders as completed")
            elif payment_intent.status in ('canceled', 'requires_payment_method'):
                updated = Order.objects.filter(
                    stripe_payment_intent_id=payment_intent_id,
                    status='pending',
                ).update(status='cancelled')
                logger.info(f"Reconciled PaymentIntent {payment_intent_id} - marked {updated} orders as cancelled")
        except stripe.error.StripeError as e:
            logger.warning(f"Failed to reconcile PaymentIntent {payment_intent_id}: {e}")

    logger.info(f"Reconciliation complete: {reconciled} orders updated")

    # Reschedule this task to run again
    reconcile_pending_orders.enqueue(
        run_after=timezone.now() + timedelta(minutes=RECONCILIATION_INTERVAL_MINUTES)
    )

    return reconciled
