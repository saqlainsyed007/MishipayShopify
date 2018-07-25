from datetime import datetime
from django import template


register = template.Library()


@register.simple_tag()
def get_amount(quantity, price, *args, **kwargs):
    return round(float(quantity) * float(price), 2)


@register.filter()
def format_date_string(datetime_string):
    # Remove last ':' from date string in order for python
    # to recognise it as timezone.
    datetime_string = datetime_string[::-1].replace(":", "", 1)[::-1]
    datetime_obj = datetime.strptime(datetime_string, '%Y-%m-%dT%H:%M:%S%z')
    return datetime_obj.strftime('%b %d, %Y')
