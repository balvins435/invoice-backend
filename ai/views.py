from django.shortcuts import render

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .services.invoice_ai import generate_invoice_from_text

@api_view(['POST'])
def generate_invoice(request):
    text = request.data.get("text")

    if not text:
        return Response({"error": "Text is required"}, status=400)

    data = generate_invoice_from_text(text)
    return Response(data)