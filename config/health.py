from django.db import Error, connection
from django.http import JsonResponse


def healthz(request):
    """Liveness + DB reachability for load balancers, docker health checks and deploy smoke tests."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Error:
        return JsonResponse({"status": "error"}, status=503)
    return JsonResponse({"status": "ok"})
