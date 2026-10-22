# Rutas de la API

Generado con `bash scripts/exportar-contrato.sh` desde el código; no editar a mano.

Convenciones que valen para todas (ver `docs/contrato/LEEME.md`): prefijo `/api/v1/`, barra final,
JSON en snake_case, autenticación `Authorization: Bearer <access>`, listas paginadas como
`{count, next, previous, results}` con 20 por página.

204 rutas.

| Ruta | Métodos | Vista | Código | Permisos | Serializador | Paginada |
|---|---|---|---|---|---|---|
| `/api/v1/agenda/view/` | GET | AgendaViewList | `django-api/apps/agenda/views.py:218` | rol: admin/reception/doctor/auxiliary | AppointmentSerializer | sí |
| `/api/v1/app/citas/` | GET | MisCitasView | `django-api/apps/app_paciente/views.py:101` | EsPaciente, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/app/citas/<uuid:pk>/confirmar/` | POST | ConfirmarCitaView | `django-api/apps/app_paciente/views.py:335` | EsPaciente, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/app/clinica/` | GET | MiClinicaView | `django-api/apps/app_paciente/views.py:231` | EsPaciente, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/app/cuenta/` | GET | MiCuentaView | `django-api/apps/app_paciente/views.py:38` | EsPaciente |  |  |
| `/api/v1/app/indicaciones/` | GET | MisIndicacionesView | `django-api/apps/app_paciente/views.py:150` | EsPaciente, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/app/logros/` | GET | MisLogrosView | `django-api/apps/app_paciente/views.py:179` | EsPaciente, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/app/me/` | GET | MiPerfilView | `django-api/apps/app_paciente/views.py:65` | EsPaciente, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/app/mensajes/` | GET POST | MisMensajesView | `django-api/apps/app_paciente/contacto.py:141` | EsPaciente, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/app/saldo/` | GET | MiSaldoView | `django-api/apps/app_paciente/views.py:121` | EsPaciente, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/app/solicitudes-cita/` | GET POST | MisSolicitudesCitaView | `django-api/apps/app_paciente/contacto.py:97` | EsPaciente, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/appointments/` | GET POST | AppointmentListCreateView | `django-api/apps/agenda/views.py:45` | IsAuthenticated · varía por método (get_permissions) | AppointmentSerializer | sí |
| `/api/v1/appointments/<uuid:pk>/` | GET PUT PATCH | AppointmentDetailView | `django-api/apps/agenda/views.py:104` | IsAuthenticated · varía por método (get_permissions) | AppointmentSerializer |  |
| `/api/v1/appointments/<uuid:pk>/cancel/` | POST | AppointmentCancelView | `django-api/apps/agenda/views.py:137` | TieneFuncion(agenda) |  |  |
| `/api/v1/appointments/<uuid:pk>/checkin/` | POST | AppointmentCheckinView | `django-api/apps/agenda/views.py:176` | TieneFuncion(agenda) |  |  |
| `/api/v1/appointments/<uuid:pk>/checkout/` | POST | AppointmentCheckoutView | `django-api/apps/agenda/views.py:205` | rol: admin/reception/doctor |  |  |
| `/api/v1/appointments/<uuid:pk>/confirm/` | POST | AppointmentConfirmView | `django-api/apps/agenda/views.py:127` | TieneFuncion(agenda) |  |  |
| `/api/v1/appointments/<uuid:pk>/reschedule/` | POST | AppointmentRescheduleView | `django-api/apps/agenda/views.py:147` | TieneFuncion(agenda) |  |  |
| `/api/v1/appointments/<uuid:pk>/start/` | POST | AppointmentStartView | `django-api/apps/agenda/views.py:259` | TieneFuncion(agenda) |  |  |
| `/api/v1/appointments/waiting/` | GET | WaitingPatientsView | `django-api/apps/agenda/views.py:362` | rol: admin/reception/doctor/auxiliary |  |  |
| `/api/v1/audit-logs/` | GET | AuditLogListView | `django-api/apps/accounts/views.py:458` | rol: admin | AuditLogSerializer | sí |
| `/api/v1/auth/change-password/` | POST | CambiarMiContrasenaView | `django-api/apps/accounts/password_views.py:17` | IsAuthenticated |  |  |
| `/api/v1/auth/google/` | POST | GoogleLoginView | `django-api/apps/accounts/google.py:83` | AllowAny |  |  |
| `/api/v1/auth/google/config/` | GET | GoogleConfigView | `django-api/apps/accounts/google.py:75` | AllowAny |  |  |
| `/api/v1/auth/login/` | POST | StaffLoginView | `django-api/apps/accounts/views.py:53` | público | StaffLoginSerializer |  |
| `/api/v1/auth/me/` | GET | MeView | `django-api/apps/accounts/views.py:488` | IsAuthenticated |  |  |
| `/api/v1/auth/me/preferencias/` | GET PATCH | PreferenciasView | `django-api/apps/accounts/views.py:557` | IsAuthenticated |  |  |
| `/api/v1/auth/otp/canal/` | GET | OTPCanalView | `django-api/apps/accounts/views.py:59` | AllowAny |  |  |
| `/api/v1/auth/otp/request/` | POST | OTPRequestView | `django-api/apps/accounts/views.py:72` | AllowAny |  |  |
| `/api/v1/auth/otp/verify/` | POST | OTPVerifyView | `django-api/apps/accounts/views.py:209` | AllowAny |  |  |
| `/api/v1/auth/recovery/confirm/` | POST | StaffRecoveryConfirmView | `django-api/apps/accounts/views.py:307` | AllowAny |  |  |
| `/api/v1/auth/recovery/request/` | POST | StaffRecoveryRequestView | `django-api/apps/accounts/views.py:260` | AllowAny |  |  |
| `/api/v1/auth/token/refresh/` | POST | TokenRefreshView | `rest_framework_simplejwt.views` | público |  |  |
| `/api/v1/bandeja-app/mensajes/` | GET | MensajesBandejaView | `django-api/apps/app_paciente/contacto.py:284` | rol: admin/reception/doctor/auxiliary, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/bandeja-app/mensajes/<uuid:pk>/responder/` | POST | ResponderMensajeView | `django-api/apps/app_paciente/contacto.py:296` | TieneFuncion(mensajes_app) |  |  |
| `/api/v1/bandeja-app/resumen/` | GET | ResumenBandejaView | `django-api/apps/app_paciente/contacto.py:168` | rol: admin/reception/doctor/auxiliary, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/bandeja-app/solicitudes/` | GET | SolicitudesBandejaView | `django-api/apps/app_paciente/contacto.py:182` | rol: admin/reception/doctor/auxiliary, RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/bandeja-app/solicitudes/<uuid:pk>/agendar/` | POST | AgendarSolicitudView | `django-api/apps/app_paciente/contacto.py:205` | TieneFuncion(agenda), RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/bandeja-app/solicitudes/<uuid:pk>/rechazar/` | POST | RechazarSolicitudView | `django-api/apps/app_paciente/contacto.py:264` | TieneFuncion(agenda), RequiereFuncionalidad(app_paciente) |  |  |
| `/api/v1/budgets/<uuid:pk>/` | GET PUT PATCH | BudgetDetailView | `django-api/apps/billing/views.py:58` | TieneFuncion(cobros) | BudgetSerializer |  |
| `/api/v1/budgets/<uuid:pk>/approve/` | POST | BudgetApproveView | `django-api/apps/billing/views.py:82` | TieneFuncion(cobros) |  |  |
| `/api/v1/budgets/<uuid:pk>/generate-payment-plan/` | POST | GeneratePaymentPlanView | `django-api/apps/billing/views.py:94` | TieneFuncion(cobros) |  |  |
| `/api/v1/budgets/<uuid:pk>/items/` | POST | BudgetItemCreateView | `django-api/apps/billing/views.py:68` | TieneFuncion(cobros) | BudgetItemSerializer |  |
| `/api/v1/cie10/` | GET | Cie10SearchView | `django-api/apps/clinical/form033_views.py:101` | rol: admin/doctor/auxiliary/reception |  |  |
| `/api/v1/clinical/follow-ups/` | GET | FollowUpAlertsView | `django-api/apps/clinical/sprint22_views.py:208` | rol: admin/doctor/auxiliary/reception |  |  |
| `/api/v1/clinical/plan-template-items/<uuid:pk>/` | DELETE | TemplateItemDeleteView | `django-api/apps/clinical/sprint22_views.py:339` | rol: admin/doctor |  |  |
| `/api/v1/clinical/plan-templates/` | GET POST | TemplateListCreateView | `django-api/apps/clinical/sprint22_views.py:33` | IsAuthenticated · varía por método (get_permissions) | TreatmentPlanTemplateSerializer |  |
| `/api/v1/clinical/plan-templates/<uuid:pk>/items/` | POST | TemplateItemCreateView | `django-api/apps/clinical/sprint22_views.py:312` | rol: admin/doctor |  |  |
| `/api/v1/config/agreements/` | GET POST | AgreementListCreateView | `django-api/apps/configuration/views.py:59` | IsAuthenticated | AgreementSerializer | sí |
| `/api/v1/config/agreements/<uuid:pk>/` | GET PUT PATCH DELETE | AgreementDetailView | `django-api/apps/configuration/views.py:76` | IsAuthenticated | AgreementSerializer |  |
| `/api/v1/config/backup/` | POST | TenantBackupView | `django-api/apps/configuration/views.py:376` | PuedeRespaldar |  |  |
| `/api/v1/config/backup/decrypt/` | POST | TenantBackupDecryptView | `django-api/apps/configuration/views.py:455` | PuedeRespaldar |  |  |
| `/api/v1/config/backup/herramientas/` | GET | TenantBackupToolsView | `django-api/apps/configuration/views.py:436` | PuedeRespaldar |  |  |
| `/api/v1/config/branding/` | GET PATCH | ClinicBrandingView | `django-api/apps/configuration/views.py:192` | rol: admin/reception/doctor/auxiliary |  |  |
| `/api/v1/config/document-appearance/` | GET PATCH DELETE | DocumentAppearanceView | `django-api/apps/configuration/views.py:277` | rol: admin/reception/doctor/auxiliary |  |  |
| `/api/v1/config/modulos/` | GET PATCH | ModulosClinicaView | `django-api/apps/configuration/views.py:538` | IsClinicAdmin |  |  |
| `/api/v1/config/parameters/` | GET | SystemParameterListView | `django-api/apps/configuration/views.py:172` | rol: admin | SystemParameterSerializer | sí |
| `/api/v1/config/parameters/<uuid:pk>/` | GET PUT PATCH | SystemParameterDetailView | `django-api/apps/configuration/views.py:182` | rol: admin | SystemParameterSerializer |  |
| `/api/v1/config/price-matrix/` | GET PUT | PriceMatrixView | `django-api/apps/configuration/views.py:100` | rol: admin/reception/doctor/auxiliary · varía por método (get_permissions) |  |  |
| `/api/v1/config/tarifarios/` | GET POST | TariffListCreateView | `django-api/apps/configuration/views.py:83` | IsAuthenticated | TariffSerializer | sí |
| `/api/v1/config/tarifarios/<uuid:pk>/` | GET PUT PATCH DELETE | TariffDetailView | `django-api/apps/configuration/views.py:93` | IsAuthenticated | TariffSerializer |  |
| `/api/v1/config/temas/previsualizar/` | POST | TemasPrevisualizarView | `django-api/apps/configuration/views.py:250` | rol: admin/superadmin |  |  |
| `/api/v1/config/treatments/` | GET POST | TreatmentListCreateView | `django-api/apps/configuration/views.py:38` | IsAuthenticated | TreatmentSerializer | sí |
| `/api/v1/config/treatments/<uuid:pk>/` | GET PUT PATCH DELETE | TreatmentDetailView | `django-api/apps/configuration/views.py:52` | IsAuthenticated | TreatmentSerializer |  |
| `/api/v1/config/whatsapp-templates/` | GET POST | WhatsAppTemplateListCreateView | `django-api/apps/whatsapp/views.py:16` | rol: admin | WhatsAppTemplateSerializer | sí |
| `/api/v1/config/whatsapp/` | GET PATCH | ConfiguracionWhatsAppView | `django-api/apps/whatsapp/config_views.py:42` | PuedeGestionarWhatsApp, RequiereFuncionalidad(whatsapp) |  |  |
| `/api/v1/consent-templates/` | GET POST | ConsentTemplateListCreateView | `django-api/apps/clinical/views.py:557` | rol: admin/doctor |  | sí |
| `/api/v1/consent-templates/<uuid:pk>/` | GET PUT PATCH DELETE | ConsentTemplateDetailView | `django-api/apps/clinical/views.py:578` | rol: admin/doctor |  |  |
| `/api/v1/consents/<uuid:pk>/detail/` | GET PUT PATCH | ConsentDetailView | `django-api/apps/clinical/views.py:592` | rol: admin/doctor |  |  |
| `/api/v1/consents/<uuid:pk>/pdf/` | GET | ConsentPDFView | `django-api/apps/clinical/form033_views.py:445` | rol: admin/doctor/reception/auxiliary |  |  |
| `/api/v1/consents/<uuid:pk>/sign/` | POST | ConsentSignView | `django-api/apps/clinical/views.py:339` | rol: admin/doctor/reception |  |  |
| `/api/v1/doctors/` | GET | DoctorListView | `django-api/apps/agenda/views.py:28` | rol: admin/reception/doctor/auxiliary | DoctorSerializer | sí |
| `/api/v1/doctors/<uuid:pk>/calendar-url/` | GET | DoctorCalendarURLView | `django-api/apps/agenda/views.py:288` | rol: admin/doctor |  |  |
| `/api/v1/doctors/<uuid:pk>/fees/` | GET POST | DoctorFeeListCreateView | `django-api/apps/billing/views.py:245` | rol: admin | DoctorFeeSerializer | sí |
| `/api/v1/doctors/me/signature/` | GET POST | DoctorMySignatureView | `django-api/apps/agenda/views.py:321` | rol: doctor/admin |  |  |
| `/api/v1/evolutions/<uuid:pk>/` | GET PUT PATCH DELETE | EvolutionDetailView | `django-api/apps/clinical/views.py:506` | rol: admin/doctor/auxiliary |  |  |
| `/api/v1/evolutions/<uuid:pk>/prescription-pdf/` | GET | PrescriptionPDFView | `django-api/apps/clinical/sprint22_views.py:239` | rol: admin/doctor/auxiliary/reception |  |  |
| `/api/v1/exam-requests/<uuid:pk>/report/` | PATCH | ExamRequestReportView | `django-api/apps/clinical/form033_views.py:164` | rol: admin/doctor/auxiliary |  |  |
| `/api/v1/finanzas/caja/` | GET POST | CajaView | `django-api/apps/finanzas/views.py:287` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/categorias/` | GET POST | CategoriasView | `django-api/apps/finanzas/views.py:118` | TieneFuncion(finanzas) | CategoriaSerializer |  |
| `/api/v1/finanzas/categorias/<uuid:pk>/` | PUT PATCH | CategoriaView | `django-api/apps/finanzas/views.py:130` | TieneFuncion(finanzas) | CategoriaSerializer |  |
| `/api/v1/finanzas/cobros/` | GET PATCH | CobrosView | `django-api/apps/finanzas/views.py:749` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/cobros/<uuid:pk>/` | GET PATCH | CobrosView | `django-api/apps/finanzas/views.py:749` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/cobros/<uuid:pk>/comprobante/` | GET | ComprobanteCobroView | `django-api/apps/finanzas/views.py:722` | TieneFuncion(cobros), RequiereFuncionalidad(finanzas) |  |  |
| `/api/v1/finanzas/configuracion/` | GET PATCH | ConfiguracionView | `django-api/apps/finanzas/views.py:101` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/decimos/` | GET POST | DecimosView | `django-api/apps/finanzas/views.py:677` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/egresos/` | GET POST | EgresosView | `django-api/apps/finanzas/views.py:140` | TieneFuncion(finanzas) | EgresoSerializer |  |
| `/api/v1/finanzas/egresos/<uuid:pk>/` | GET PUT PATCH | EgresoView | `django-api/apps/finanzas/views.py:203` | TieneFuncion(finanzas) | EgresoSerializer |  |
| `/api/v1/finanzas/egresos/<uuid:pk>/anular/` | POST | AnularEgresoView | `django-api/apps/finanzas/views.py:231` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/egresos/<uuid:pk>/comprobante/` | GET | ComprobanteEgresoView | `django-api/apps/finanzas/views.py:273` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/egresos/<uuid:pk>/pagar/` | POST | PagarEgresoView | `django-api/apps/finanzas/views.py:253` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/equipo/` | GET | EquipoView | `django-api/apps/finanzas/views.py:333` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/equipo/<uuid:pk>/` | PATCH | PerfilView | `django-api/apps/finanzas/views.py:348` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/exportar/` | GET | ExportarView | `django-api/apps/finanzas/views.py:796` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/liquidaciones/` | GET POST | LiquidacionesView | `django-api/apps/finanzas/views.py:388` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/liquidaciones/<uuid:pk>/anular/` | POST | AnularLiquidacionView | `django-api/apps/finanzas/views.py:444` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/liquidaciones/<uuid:pk>/pagar/` | POST | PagarLiquidacionView | `django-api/apps/finanzas/views.py:419` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/liquidaciones/<uuid:pk>/pdf/` | GET | LiquidacionPdfView | `django-api/apps/finanzas/views.py:463` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/liquidaciones/previa/` | GET | LiquidacionPreviaView | `django-api/apps/finanzas/views.py:377` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/obligaciones/` | GET POST | ObligacionesView | `django-api/apps/finanzas/views.py:639` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/resumen/` | GET | ResumenView | `django-api/apps/finanzas/views.py:79` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/roles/` | GET POST | RolesView | `django-api/apps/finanzas/views.py:507` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/roles/<uuid:pk>/anular/` | POST | AnularRolView | `django-api/apps/finanzas/views.py:602` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/roles/<uuid:pk>/pagar/` | POST | PagarRolView | `django-api/apps/finanzas/views.py:576` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/roles/<uuid:pk>/pdf/` | GET | RolPdfView | `django-api/apps/finanzas/views.py:618` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/roles/generar/` | POST | GenerarRolesView | `django-api/apps/finanzas/views.py:549` | TieneFuncion(finanzas) |  |  |
| `/api/v1/finanzas/roles/previa/` | GET | RolPreviaView | `django-api/apps/finanzas/views.py:497` | TieneFuncion(finanzas) |  |  |
| `/api/v1/form033/<uuid:pk>/` | GET PUT PATCH | Form033DetailView | `django-api/apps/clinical/form033_views.py:86` | rol: admin/doctor/auxiliary | Form033Serializer |  |
| `/api/v1/health/` | GET | HealthView | `django-api/apps/common/health.py:44` | AllowAny |  |  |
| `/api/v1/installments/<uuid:pk>/pay/` | POST | PayInstallmentView | `django-api/apps/billing/views.py:173` | TieneFuncion(cobros) |  |  |
| `/api/v1/inventory/alerts/expiring/` | GET | ExpiringBatchAlertView | `django-api/apps/inventory/views.py:115` | rol: admin/auxiliary/doctor/reception, RequiereFuncionalidad(inventario) |  |  |
| `/api/v1/inventory/alerts/low-stock/` | GET | LowStockAlertView | `django-api/apps/inventory/views.py:94` | rol: admin/auxiliary/doctor/reception, RequiereFuncionalidad(inventario) |  |  |
| `/api/v1/inventory/movements/` | GET | InventoryMovementListView | `django-api/apps/inventory/views.py:148` | rol: admin/auxiliary/doctor/reception, RequiereFuncionalidad(inventario) | InventoryMovementSerializer | sí |
| `/api/v1/legal/condiciones/` | GET | CondicionesView | `django-api/apps/common/legal_views.py:41` | AllowAny |  |  |
| `/api/v1/legal/condiciones/aceptar/` | POST | AceptarCondicionesView | `django-api/apps/common/legal_views.py:60` | rol: admin |  |  |
| `/api/v1/legal/privacidad/` | GET | AvisoPrivacidadView | `django-api/apps/common/legal_views.py:36` | AllowAny |  |  |
| `/api/v1/logros/` | GET POST | LogroListCreateView | `django-api/apps/logros/views.py:28` | PuedeGestionarLogros, RequiereFuncionalidad(logros) | LogroSerializer |  |
| `/api/v1/logros/<uuid:pk>/` | GET PUT PATCH DELETE | LogroDetailView | `django-api/apps/logros/views.py:42` | PuedeGestionarLogros, RequiereFuncionalidad(logros) | LogroSerializer |  |
| `/api/v1/logros/evaluar/` | POST | EvaluarLogrosView | `django-api/apps/logros/views.py:105` | PuedeGestionarLogros, RequiereFuncionalidad(logros) |  |  |
| `/api/v1/logros/otorgar/` | POST | OtorgarLogroView | `django-api/apps/logros/views.py:60` | PuedeGestionarLogros, RequiereFuncionalidad(logros) |  |  |
| `/api/v1/me/device-tokens/` | POST | DeviceTokenRegisterView | `django-api/apps/accounts/views.py:469` | IsAuthenticated | DeviceTokenSerializer |  |
| `/api/v1/odontogram-states/` | GET | OdontogramStateListView | `django-api/apps/clinical/views.py:208` | rol: admin/doctor/auxiliary |  |  |
| `/api/v1/patients/` | GET POST | PatientListCreateView | `django-api/apps/patients/views.py:23` | IsAuthenticated · varía por método (get_permissions) |  | sí |
| `/api/v1/patients/<uuid:pk>/` | GET PUT PATCH DELETE | PatientDetailView | `django-api/apps/patients/views.py:92` | IsAuthenticated · varía por método (get_permissions) | PatientSerializer |  |
| `/api/v1/patients/<uuid:pk>/account-statement/` | GET | PatientAccountStatementView | `django-api/apps/billing/views.py:210` | rol: admin/reception/doctor |  |  |
| `/api/v1/patients/<uuid:pk>/alertas/` | GET | AlertasPacienteView | `django-api/apps/clinical/alertas_views.py:38` | rol: admin/doctor/auxiliary |  |  |
| `/api/v1/patients/<uuid:pk>/alertas/revisar/` | POST | RevisarRecetaView | `django-api/apps/clinical/alertas_views.py:45` | rol: admin/doctor/auxiliary |  |  |
| `/api/v1/patients/<uuid:pk>/app-access/` | GET POST DELETE | AccesoAppView | `django-api/apps/patients/acceso_app.py:85` | rol: admin/reception |  |  |
| `/api/v1/patients/<uuid:pk>/apply-plan-template/` | POST | ApplyTemplateView | `django-api/apps/clinical/sprint22_views.py:72` | rol: admin/doctor/auxiliary |  |  |
| `/api/v1/patients/<uuid:pk>/aviso-privacidad/` | GET POST | AvisoPrivacidadView | `django-api/apps/patients/views.py:248` | rol: admin/reception |  |  |
| `/api/v1/patients/<uuid:pk>/budgets/` | GET POST | BudgetListCreateView | `django-api/apps/billing/views.py:38` | rol: admin/reception/doctor | BudgetSerializer | sí |
| `/api/v1/patients/<uuid:pk>/certificado-atencion/` | GET POST | CertificadoAtencionView | `django-api/apps/clinical/certificado_views.py:52` | rol: admin/doctor/reception |  |  |
| `/api/v1/patients/<uuid:pk>/clinical-record/` | GET PUT PATCH | ClinicalRecordView | `django-api/apps/clinical/views.py:53` | rol: admin/doctor/auxiliary | ClinicalRecordSerializer |  |
| `/api/v1/patients/<uuid:pk>/clinical-record/export-pdf/` | GET | ClinicalHistoryExportView | `django-api/apps/clinical/views.py:428` | rol: admin/doctor |  |  |
| `/api/v1/patients/<uuid:pk>/consents/` | GET POST | InformedConsentListCreateView | `django-api/apps/clinical/views.py:311` | rol: admin/doctor/reception |  | sí |
| `/api/v1/patients/<uuid:pk>/cpo-ceo/` | GET | CpoCeoIndexView | `django-api/apps/clinical/form033_views.py:192` | rol: admin/doctor/auxiliary/reception |  |  |
| `/api/v1/patients/<uuid:pk>/diagnoses/` | GET POST | DiagnosisListCreateView | `django-api/apps/clinical/views.py:89` | rol: admin/doctor/auxiliary | DiagnosisSerializer | sí |
| `/api/v1/patients/<uuid:pk>/documents/` | GET POST | PatientDocumentListCreateView | `django-api/apps/patients/views.py:138` | rol: admin/reception/doctor | PatientDocumentSerializer | sí |
| `/api/v1/patients/<uuid:pk>/documents/<int:doc_id>/` | DELETE | PatientDocumentDeleteView | `django-api/apps/patients/views.py:197` | rol: admin/doctor |  |  |
| `/api/v1/patients/<uuid:pk>/documents/<int:doc_id>/file/` | GET | PatientDocumentFileView | `django-api/apps/patients/views.py:158` | rol: admin/reception/doctor/auxiliary |  |  |
| `/api/v1/patients/<uuid:pk>/evolutions/` | GET POST | EvolutionListCreateView | `django-api/apps/clinical/views.py:67` | rol: admin/doctor/auxiliary | EvolutionSerializer | sí |
| `/api/v1/patients/<uuid:pk>/exam-requests/` | GET POST | ExamRequestListCreateView | `django-api/apps/clinical/form033_views.py:144` | IsAuthenticated · varía por método (get_permissions) | ExamRequestSerializer |  |
| `/api/v1/patients/<uuid:pk>/exam-requests/<uuid:exam_id>/pdf/` | GET | ExamRequestPDFView | `django-api/apps/clinical/form033_views.py:371` | rol: admin/doctor/auxiliary/reception |  |  |
| `/api/v1/patients/<uuid:pk>/form033/` | GET POST | Form033ListCreateView | `django-api/apps/clinical/form033_views.py:62` | IsAuthenticated · varía por método (get_permissions) | Form033Serializer |  |
| `/api/v1/patients/<uuid:pk>/form033/export-pdf/` | GET | Form033PDFExportView | `django-api/apps/clinical/form033_views.py:250` | rol: admin/doctor/auxiliary/reception |  |  |
| `/api/v1/patients/<uuid:pk>/form033/export-xlsx/` | GET | Form033XlsxExportView | `django-api/apps/clinical/form033_views.py:333` | rol: admin/doctor/auxiliary/reception |  |  |
| `/api/v1/patients/<uuid:pk>/logros/` | GET | LogrosDelPacienteView | `django-api/apps/logros/views.py:92` | PuedeGestionarLogros, RequiereFuncionalidad(logros) | LogroDePacienteSerializer |  |
| `/api/v1/patients/<uuid:pk>/medical-background/` | GET PUT PATCH | MedicalBackgroundView | `django-api/apps/patients/views.py:109` | rol: admin/doctor/auxiliary | MedicalBackgroundSerializer |  |
| `/api/v1/patients/<uuid:pk>/odontogram/current/` | GET | CurrentOdontogramView | `django-api/apps/clinical/views.py:253` | rol: admin/doctor/auxiliary |  |  |
| `/api/v1/patients/<uuid:pk>/payments/` | GET POST | PatientPaymentListCreateView | `django-api/apps/billing/views.py:563` | TieneFuncion(cobros) |  | sí |
| `/api/v1/patients/<uuid:pk>/periodontal-exams/` | GET POST | PeriodontalExamListCreateView | `django-api/apps/clinical/views.py:627` | rol: admin/doctor |  | sí |
| `/api/v1/patients/<uuid:pk>/radiographs/` | GET POST | RadiographPhotoListCreateView | `django-api/apps/clinical/views.py:288` | rol: admin/doctor/auxiliary |  | sí |
| `/api/v1/patients/<uuid:pk>/specialty-forms/` | GET POST | PatientSpecialtyFormListCreateView | `django-api/apps/specialties/views.py:70` | rol: admin/doctor | SpecialtyFormSerializer | sí |
| `/api/v1/patients/<uuid:pk>/tooth-records/` | GET POST | ToothRecordListCreateView | `django-api/apps/clinical/views.py:226` | rol: admin/doctor/auxiliary |  | sí |
| `/api/v1/patients/<uuid:pk>/treatment-history/` | GET | PatientTreatmentHistoryView | `django-api/apps/patients/views.py:221` | rol: admin/reception/doctor/auxiliary |  |  |
| `/api/v1/patients/<uuid:pk>/treatment-plans/` | GET POST | TreatmentPlanListCreateView | `django-api/apps/clinical/views.py:106` | rol: admin/doctor/auxiliary | TreatmentPlanSerializer | sí |
| `/api/v1/patients/<uuid:pk>/whatsapp-optin/` | GET POST | WhatsAppOptInListCreateView | `django-api/apps/whatsapp/views.py:29` | rol: admin/reception | WhatsAppOptInSerializer | sí |
| `/api/v1/patients/birthdays/` | GET | BirthdaysView | `django-api/apps/billing/views.py:593` | rol: admin/reception/doctor/auxiliary |  |  |
| `/api/v1/payment-plans/<uuid:pk>/installments/` | GET | PaymentPlanInstallmentsView | `django-api/apps/billing/views.py:147` | (rol: admin/reception/doctor o TieneFuncion(cobros)) | InstallmentSerializer | sí |
| `/api/v1/periodontal-exams/<uuid:pk>/` | GET PUT PATCH DELETE | PeriodontalExamDetailView | `django-api/apps/clinical/views.py:677` | rol: admin/doctor |  |  |
| `/api/v1/periodontal-exams/<uuid:pk>/pdf/` | GET | PeriodontalExamPDFView | `django-api/apps/clinical/views.py:699` | rol: admin/doctor |  |  |
| `/api/v1/periodontal-teeth/<uuid:pk>/` | GET PUT PATCH | PeriodontalToothUpdateView | `django-api/apps/clinical/views.py:742` | rol: admin/doctor |  |  |
| `/api/v1/platform/audit/` | GET | PlatformAuditView | `django-api/apps/common/platform_views.py:451` | rol: superadmin |  |  |
| `/api/v1/platform/clinics/` | GET POST | ClinicListCreateView | `django-api/apps/common/platform_views.py:146` | rol: superadmin | ClinicSerializer |  |
| `/api/v1/platform/clinics/<uuid:pk>/` | GET PUT PATCH | ClinicDetailView | `django-api/apps/common/platform_views.py:217` | rol: superadmin | ClinicSerializer |  |
| `/api/v1/platform/clinics/<uuid:pk>/admin/` | GET POST PATCH | ClinicAdminView | `django-api/apps/common/platform_views.py:309` | rol: superadmin |  |  |
| `/api/v1/platform/clinics/<uuid:pk>/admin/reset-password/` | POST | ClinicAdminResetPasswordView | `django-api/apps/common/platform_views.py:399` | rol: superadmin |  |  |
| `/api/v1/platform/clinics/<uuid:pk>/identidad/` | GET PATCH | ClinicIdentidadView | `django-api/apps/common/platform_views.py:250` | rol: superadmin |  |  |
| `/api/v1/platform/config/` | GET PATCH | PlatformConfigView | `django-api/apps/common/platform_views.py:578` | rol: superadmin |  |  |
| `/api/v1/platform/config/correo-de-prueba/` | POST | CorreoDePruebaView | `django-api/apps/common/platform_views.py:594` | rol: superadmin |  |  |
| `/api/v1/platform/funcionalidades/` | GET | FuncionalidadesView | `django-api/apps/common/platform_views.py:525` | rol: superadmin |  |  |
| `/api/v1/platform/funcionalidades/<str:clave>/` | PATCH | FuncionalidadPublicacionView | `django-api/apps/common/platform_views.py:551` | rol: superadmin |  |  |
| `/api/v1/platform/overview/` | GET | PlatformOverviewView | `django-api/apps/common/platform_views.py:432` | rol: superadmin |  |  |
| `/api/v1/platform/solicitudes/` | GET | SolicitudesPlataformaView | `django-api/apps/common/solicitudes.py:195` | rol: superadmin | SolicitudPlataformaSerializer |  |
| `/api/v1/platform/solicitudes/<uuid:pk>/` | PUT PATCH | SolicitudPlataformaView | `django-api/apps/common/solicitudes.py:210` | rol: superadmin | SolicitudPlataformaSerializer |  |
| `/api/v1/platform/solicitudes/<uuid:pk>/aprobar/` | POST | AprobarSolicitudView | `django-api/apps/common/solicitudes.py:233` | rol: superadmin |  |  |
| `/api/v1/platform/solicitudes/<uuid:pk>/reenviar/` | POST | ReenviarEnlaceView | `django-api/apps/common/solicitudes.py:266` | rol: superadmin |  |  |
| `/api/v1/products/` | GET POST | ProductListCreateView | `django-api/apps/inventory/views.py:24` | IsAuthenticated · varía por método (get_permissions) | ProductSerializer | sí |
| `/api/v1/products/<uuid:pk>/` | GET PUT PATCH | ProductDetailView | `django-api/apps/inventory/views.py:42` | TieneFuncion(inventario), RequiereFuncionalidad(inventario) | ProductSerializer |  |
| `/api/v1/products/<uuid:pk>/batches/` | GET POST | BatchListCreateView | `django-api/apps/inventory/views.py:50` | TieneFuncion(inventario), RequiereFuncionalidad(inventario) | BatchSerializer | sí |
| `/api/v1/publico/solicitudes/` | POST | SolicitudPublicaView | `django-api/apps/common/solicitudes.py:90` | AllowAny |  |  |
| `/api/v1/ready/` | GET | ReadyView | `django-api/apps/common/health.py:55` | AllowAny |  |  |
| `/api/v1/reports/appointments-summary/` | GET | AppointmentsSummaryReportView | `django-api/apps/billing/views.py:525` | TieneFuncion(reportes) |  |  |
| `/api/v1/reports/delinquency/` | GET | DelinquencyReportView | `django-api/apps/billing/views.py:342` | TieneFuncion(cobros) |  |  |
| `/api/v1/reports/financial/` | GET | FinancialReportView | `django-api/apps/billing/views.py:261` | TieneFuncion(reportes), RequiereFuncionalidad(reportes) |  |  |
| `/api/v1/reports/inventory/` | GET | InventoryReportView | `django-api/apps/billing/views.py:479` | TieneFuncion(inventario) |  |  |
| `/api/v1/reports/new-patients/` | GET | NewPatientsReportView | `django-api/apps/billing/views.py:427` | TieneFuncion(reportes) |  |  |
| `/api/v1/reports/production-by-doctor/` | GET | ProductionByDoctorReportView | `django-api/apps/billing/views.py:393` | rol: admin/doctor |  |  |
| `/api/v1/schema/` | GET | SpectacularAPIView | `drf_spectacular.views` | AllowAny |  |  |
| `/api/v1/schema/swagger-ui/` | GET | SpectacularSwaggerView | `drf_spectacular.views` | AllowAny |  |  |
| `/api/v1/specialties/` | GET POST | SpecialtyListCreateView | `django-api/apps/specialties/views.py:23` | IsAuthenticated · varía por método (get_permissions) | SpecialtySerializer | sí |
| `/api/v1/specialties/<uuid:pk>/` | GET PUT PATCH DELETE | SpecialtyDetailView | `django-api/apps/specialties/views.py:38` | IsAuthenticated · varía por método (get_permissions) | SpecialtySerializer |  |
| `/api/v1/specialties/<uuid:pk>/form-template/` | GET | SpecialtyFormTemplateView | `django-api/apps/specialties/views.py:52` | rol: admin/reception/doctor/auxiliary |  |  |
| `/api/v1/specialty-forms/<uuid:pk>/` | GET PUT PATCH | SpecialtyFormDetailView | `django-api/apps/specialties/views.py:95` | rol: admin/doctor | SpecialtyFormSerializer |  |
| `/api/v1/tooth-records/<uuid:pk>/` | DELETE | ToothRecordDeleteView | `django-api/apps/clinical/views.py:472` | rol: admin/doctor/auxiliary |  |  |
| `/api/v1/treatment-plan-items/<uuid:pk>/` | PUT PATCH | TreatmentPlanItemUpdateView | `django-api/apps/clinical/views.py:156` | rol: admin/doctor/auxiliary | TreatmentPlanItemSerializer |  |
| `/api/v1/treatment-plans/<uuid:pk>/` | GET PUT PATCH | TreatmentPlanDetailView | `django-api/apps/clinical/views.py:123` | rol: admin/doctor/auxiliary | TreatmentPlanSerializer |  |
| `/api/v1/treatment-plans/<uuid:pk>/generate-budget/` | POST | PlanToBudgetView | `django-api/apps/clinical/sprint22_views.py:143` | rol: admin/reception/doctor |  |  |
| `/api/v1/treatment-plans/<uuid:pk>/items/` | POST | TreatmentPlanItemCreateView | `django-api/apps/clinical/views.py:135` | rol: admin/doctor/auxiliary | TreatmentPlanItemSerializer |  |
| `/api/v1/users/` | GET POST | UserListCreateView | `django-api/apps/accounts/views.py:348` | rol: admin | UserSerializer | sí |
| `/api/v1/users/<uuid:pk>/` | GET PUT PATCH | UserDetailView | `django-api/apps/accounts/views.py:439` | rol: admin | UserSerializer |  |
| `/api/v1/users/<uuid:pk>/invitar/` | POST | InvitarUsuarioView | `django-api/apps/accounts/views.py:403` | rol: admin |  |  |
| `/api/v1/users/funciones/` | GET | CatalogoFuncionesView | `django-api/apps/accounts/views.py:527` | rol: admin |  |  |
| `/api/v1/whatsapp-optin/<uuid:pk>/revoke/` | POST | WhatsAppOptInRevokeView | `django-api/apps/whatsapp/views.py:66` | rol: admin/reception |  |  |
