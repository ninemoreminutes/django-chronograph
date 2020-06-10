# Python
import datetime

# Django
from django.core.management.base import BaseCommand
from django.utils import timezone

# Chronograph
from chronograph.models import Log


class Command( BaseCommand ):

    help = 'Deletes old job logs.'

    def add_arguments(self, parser):
        parser.add_argument(
            'unit',
            choices=('weeks', 'days', 'hours', 'minutes'),
            help='Unit of time to clean.',
        )
        parser.add_argument(
            'amount',
            type=int,
            help='Amount of the given unit.',
        )
    
    def handle(self, *args, **options):
        unit = options.get('unit')
        amount = options.get('amount')
        time_ago = timezone.now() - datetime.timedelta(**{unit: amount})
        Log.objects.filter(run_date__lte=time_ago).delete()
