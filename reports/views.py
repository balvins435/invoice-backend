from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from business.models import Business
from .services import monthly_report


class MonthlyReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        business_id = request.query_params.get('business')
        month = request.query_params.get('month')
        year = request.query_params.get('year')

        if not all([business_id, month, year]):
            return Response(
                {"error": "business, month and year are required"},
                status=400
            )

        business = Business.objects.get(id=business_id)

        report = monthly_report(
            business=business,
            month=int(month),
            year=int(year)
        )

        return Response(report)
