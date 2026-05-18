from django import template

register = template.Library()


@register.filter
def services_summary(appointment):
    lines = list(appointment.line_items.all())
    if not lines:
        return '—'
    first = lines[0].treatment.name
    if len(lines) > 1:
        return f'{first} +{len(lines) - 1} more'
    return first
