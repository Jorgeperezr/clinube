from django.urls import path

from apps.common import health, legal_views, solicitudes
from apps.common import platform_views as views

urlpatterns = [
    # Sondas de salud: públicas y sin autenticación, porque quien las
    # consulta (Docker, un balanceador, un monitor) no tiene credenciales.
    path("health/", health.HealthView.as_view(), name="health"),
    path("ready/", health.ReadyView.as_view(), name="ready"),
    path("legal/privacidad/", legal_views.AvisoPrivacidadView.as_view(), name="legal-privacidad"),
    path("legal/condiciones/", legal_views.CondicionesView.as_view(), name="legal-condiciones"),
    path("legal/condiciones/aceptar/", legal_views.AceptarCondicionesView.as_view(),
         name="legal-condiciones-aceptar"),
    path("publico/solicitudes/", solicitudes.SolicitudPublicaView.as_view(), name="solicitud-publica"),
    path("publico/solicitudes/<uuid:pk>/confirmar/", solicitudes.ConfirmarSolicitudView.as_view(),
         name="solicitud-confirmar"),
    path("platform/solicitudes/", solicitudes.SolicitudesPlataformaView.as_view(), name="platform-solicitudes"),
    path("platform/solicitudes/<uuid:pk>/", solicitudes.SolicitudPlataformaView.as_view(),
         name="platform-solicitud"),
    path("platform/overview/", views.PlatformOverviewView.as_view(), name="platform-overview"),
    path("platform/clinics/", views.ClinicListCreateView.as_view(), name="platform-clinics"),
    path("platform/clinics/<uuid:pk>/", views.ClinicDetailView.as_view(), name="platform-clinic-detail"),
    path("platform/clinics/<uuid:pk>/admin/", views.ClinicAdminView.as_view(), name="platform-clinic-admin"),
    path("platform/clinics/<uuid:pk>/admin/reset-password/",
         views.ClinicAdminResetPasswordView.as_view(), name="platform-clinic-admin-reset"),
    path("platform/audit/", views.PlatformAuditView.as_view(), name="platform-audit"),
    path("platform/config/", views.PlatformConfigView.as_view(), name="platform-config"),
    path("platform/config/correo-de-prueba/", views.CorreoDePruebaView.as_view(),
         name="platform-correo-prueba"),
    path("platform/funcionalidades/", views.FuncionalidadesView.as_view(), name="platform-funcionalidades"),
    path("platform/funcionalidades/<str:clave>/", views.FuncionalidadPublicacionView.as_view(),
         name="platform-funcionalidad"),
    path("platform/clinics/<uuid:pk>/identidad/", views.ClinicIdentidadView.as_view(),
         name="platform-clinic-identidad"),
]
