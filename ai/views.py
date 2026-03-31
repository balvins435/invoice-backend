from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from business.models import Business

from .serializers import AIAssistantRequestSerializer, GenerateInvoiceRequestSerializer
from .services.invoice_ai import generate_assistant_response, generate_invoice_from_text
from .services.openai_service import OpenAIServiceError


class AIAssistantAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIAssistantRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        prompt = serializer.validated_data["prompt"]
        mode = serializer.validated_data["mode"]
        business = serializer.validated_data.get("business_id")

        if not business and mode == AIAssistantRequestSerializer.MODE_REPORT:
            business = Business.objects.filter(owner=request.user).order_by("id").first()
            if business is None:
                return Response(
                    {"error": "Create a business first to get AI financial reporting."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            payload = generate_assistant_response(prompt=prompt, business=business, mode=mode)
        except OpenAIServiceError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(payload, status=status.HTTP_200_OK)


class GenerateInvoiceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GenerateInvoiceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            data = generate_invoice_from_text(serializer.validated_data["text"])
        except OpenAIServiceError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(data, status=status.HTTP_200_OK)
