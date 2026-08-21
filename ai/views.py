from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AIAssistantRequestSerializer, GenerateInvoiceRequestSerializer
from .application.services import assistant_response, invoice_from_text
from .services.invoice_ai import generate_assistant_response, generate_invoice_from_text
from .services.openai_service import OpenAIServiceError as AIServiceError


class AIAssistantAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIAssistantRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        prompt = serializer.validated_data["prompt"]
        mode = serializer.validated_data["mode"]
        business = serializer.validated_data.get("business_id")

        try:
            payload = assistant_response(prompt=prompt, business=business, mode=mode, user=request.user, report_mode=AIAssistantRequestSerializer.MODE_REPORT, generator=generate_assistant_response)
        except AIServiceError as exc:
            return Response({"error": str(exc)}, status=getattr(exc, "status_code", status.HTTP_503_SERVICE_UNAVAILABLE))

        if payload is None:
            return Response({"error": "Create a business first to get AI financial reporting."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(payload, status=status.HTTP_200_OK)


class GenerateInvoiceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GenerateInvoiceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            data = invoice_from_text(serializer.validated_data["text"], generator=generate_invoice_from_text)
        except AIServiceError as exc:
            return Response({"error": str(exc)}, status=getattr(exc, "status_code", status.HTTP_503_SERVICE_UNAVAILABLE))

        return Response(data, status=status.HTTP_200_OK)
