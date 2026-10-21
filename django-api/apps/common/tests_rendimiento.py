"""
Rendimiento de la base de datos: lo que se optimizó no vuelve atrás.

  · `rango_dias` filtra exactamente lo mismo que `__date` (también en la
    pasada del CI con UTC+14), pero con un intervalo que usa el índice.
  · La auditoría y la lista de pacientes hacen las mismas consultas con 3
    filas que con 30: ninguna consulta por fila.
  · La lista de pacientes sigue contando atenciones y dando la próxima cita.
"""

from datetime import datetime, time, timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog, User
from apps.agenda.models import Appointment, Doctor
from apps.common.fechas import rango_dias
from apps.common.models import Tenant
from apps.patients.models import Patient


def _instante(dia, hora, minuto=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)), timezone.get_current_timezone())


class Base:
    def preparar(self):
        self.tenant = Tenant.objects.create(name="Rendimiento")
        self.admin = User.objects.create_user(email="a@rend.ec", password="superseguro123", role="admin",
                                              tenant=self.tenant)
        du = User.objects.create_user(email="d@rend.ec", password="superseguro123", role="doctor",
                                      tenant=self.tenant)
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=du)

    def cita(self, paciente, inicio):
        return Appointment.objects.create(tenant=self.tenant, patient=paciente, doctor=self.doctor,
                                          scheduled_start=inicio, scheduled_end=inicio + timedelta(minutes=30))


class RangoDiasTests(Base, TestCase):
    def setUp(self):
        self.preparar()

    def test_igual_que_date_en_los_bordes_del_dia(self):
        p = Patient.objects.create(tenant=self.tenant, first_name="A", last_name="B", national_id="1")
        hoy = timezone.localdate()
        ayer, manana = hoy - timedelta(days=1), hoy + timedelta(days=1)
        for dia in (ayer, hoy, manana):
            for h, m in ((0, 0), (12, 0), (23, 59)):
                self.cita(p, _instante(dia, h, m))
        citas = Appointment.objects.filter(tenant=self.tenant)
        for desde, hasta in ((hoy, hoy), (ayer, hoy), (hoy, manana), (None, hoy), (hoy, None)):
            filtro_date = {}
            if desde:
                filtro_date["scheduled_start__date__gte"] = desde
            if hasta:
                filtro_date["scheduled_start__date__lte"] = hasta
            self.assertEqual(set(citas.filter(rango_dias("scheduled_start", desde, hasta))),
                             set(citas.filter(**filtro_date)), (desde, hasta))
        self.assertEqual(citas.filter(rango_dias("scheduled_start", hoy, hoy)).count(), 3)


class SinConsultaPorFilaTests(Base, APITestCase):
    def setUp(self):
        self.preparar()
        self.client.force_authenticate(self.admin)

    def consultas(self, url):
        with CaptureQueriesContext(connection) as q:
            r = self.client.get(url)
        self.assertEqual(r.status_code, 200, r.content)
        return len(q.captured_queries)

    def test_auditoria(self):
        def registros(n):
            AuditLog.objects.bulk_create([AuditLog(tenant=self.tenant, user=self.admin, action="ver",
                                                   entity_type="Patient") for _ in range(n)])
        registros(3)
        pocas = self.consultas("/api/v1/audit-logs/")
        registros(27)
        self.assertEqual(self.consultas("/api/v1/audit-logs/"), pocas)

    def test_lista_de_pacientes(self):
        def pacientes(desde, n):
            for i in range(desde, desde + n):
                p = Patient.objects.create(tenant=self.tenant, first_name=f"N{i}", last_name=f"A{i:03d}",
                                           national_id=str(1000 + i))
                self.cita(p, timezone.now() + timedelta(days=1 + i % 5))
        pacientes(0, 3)
        pocas = self.consultas("/api/v1/patients/")
        pacientes(3, 27)
        self.assertEqual(self.consultas("/api/v1/patients/"), pocas)

    def test_atenciones_y_proxima_cita(self):
        p = Patient.objects.create(tenant=self.tenant, first_name="Ana", last_name="Paz", national_id="9")
        self.cita(p, timezone.now() - timedelta(days=30))
        self.cita(p, timezone.now() - timedelta(days=2))
        proxima = self.cita(p, timezone.now() + timedelta(days=3))
        self.cita(p, timezone.now() + timedelta(days=9))
        Patient.objects.create(tenant=self.tenant, first_name="Sin", last_name="Citas", national_id="10")
        r = self.client.get("/api/v1/patients/?ordering=attention_desc").data["results"]
        self.assertEqual([f["full_name"] for f in r], ["Ana Paz", "Sin Citas"])
        self.assertEqual([f["attention_count"] for f in r], [4, 0])
        self.assertEqual(timezone.datetime.fromisoformat(r[0]["next_appointment"]), proxima.scheduled_start)
        self.assertIsNone(r[1]["next_appointment"])
