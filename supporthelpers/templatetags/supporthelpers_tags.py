from django import template

register = template.Library()


@register.filter
def hours_and_minutes(seconds):
    if not seconds:
        return '--'
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return "%02d:%02d" % (hours, minutes)