from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from notifications.context import appointment_email_context


def generate_payment_receipt_pdf(payment) -> bytes:
    appointment = payment.appointment
    ctx = appointment_email_context(appointment)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph('Skin Sensation Spa', styles['Title']),
        Paragraph('Payment Receipt', styles['Heading2']),
        Spacer(1, 12),
    ]

    rows = [
        ['Booking reference', ctx['booking_reference']],
        ['Customer', ctx['customer_name']],
        ['Appointment', f"{ctx['appointment_date']} · {ctx['start_time']}"],
        ['Amount paid', f"K{payment.amount}"],
        ['Payment method', payment.get_payment_method_display()],
        ['Reference', payment.payment_reference or '—'],
        ['Status', payment.get_status_display()],
        ['Receipt #', str(payment.pk)],
    ]
    if payment.verified_at:
        rows.append(['Verified on', payment.verified_at.strftime('%d %b %Y %H:%M')])

    table = Table(rows, colWidths=[55 * mm, 110 * mm])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 24))
    story.append(Paragraph('Thank you for visiting Skin Sensation.', styles['Normal']))

    doc.build(story)
    return buffer.getvalue()
