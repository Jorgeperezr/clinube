"""
Copia de la clínica CON los archivos: radiografías, documentos
escaneados, consentimientos firmados y fotos.

Lo que se fija aquí:

  · que los archivos vayan dentro, enteros, y solo si se piden;
  · que lo que no entra (porque falta en el disco o no cabe) quede dicho
    en el manifiesto y no se pierda en silencio;
  · que no se cuelen archivos de otra clínica;
  · que el panel no devuelva megas de base64 al abrir la copia;
  · que descifrar.py los deje en una carpeta y no escriba fuera de ella.
"""

import base64
import gzip
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.core.files.base import ContentFile
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common import tenant_backup
from apps.common.paquete_respaldo import KIT, sacar_copia
from apps.common.tenant_backup import build_encrypted, encrypt, read_encrypted
from apps.patients.models import Patient, PatientDocument

FRASE = "frase-larga-de-prueba"
RADIOGRAFIA = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4


class CopiaConArchivos(APITestCase):
    def setUp(self):
        from apps.common.models import Tenant

        self.tenant = Tenant.objects.create(name="Clínica Sonrisa")
        self.admin = User.objects.create_user(email="admin@sonrisa.ec", password="superseguro123",
                                              role="admin", tenant=self.tenant)
        self.paciente = Patient.objects.create(tenant=self.tenant, first_name="Ana", last_name="Ríos",
                                               national_id="111")
        self.doc = PatientDocument(patient=self.paciente, doc_type="radiograph")
        self.doc.file.save("panoramica.png", ContentFile(RADIOGRAFIA), save=True)

    def abrir(self, **kw):
        blob, _ = build_encrypted(self.tenant, FRASE, requested_by=self.admin, **kw)
        return read_encrypted(blob, FRASE)

    def test_sin_pedirlos_no_van(self):
        payload = self.abrir()
        self.assertNotIn("archivos", payload)
        self.assertNotIn("archivos", payload["manifest"])

    def test_pedidos_van_enteros_y_con_su_ruta(self):
        payload = self.abrir(con_archivos=True)
        [a] = payload["archivos"]
        self.assertEqual(a["ruta"], self.doc.file.name)
        self.assertEqual(base64.b64decode(a["contenido"]), RADIOGRAFIA)
        self.assertEqual(payload["manifest"]["archivos"],
                         {"incluidos": 1, "bytes": len(RADIOGRAFIA), "omitidos": []})

    def test_el_que_falta_en_disco_se_dice(self):
        self.doc.file.storage.delete(self.doc.file.name)
        payload = self.abrir(con_archivos=True)
        self.assertEqual(payload["archivos"], [])
        [omitido] = payload["manifest"]["archivos"]["omitidos"]
        self.assertEqual(omitido["ruta"], self.doc.file.name)
        self.assertEqual(omitido["motivo"], "no está en el servidor")

    def test_lo_que_no_cabe_se_dice(self):
        with mock.patch.object(tenant_backup, "LIMITE_ARCHIVOS", 100):
            payload = self.abrir(con_archivos=True)
        self.assertEqual(payload["archivos"], [])
        self.assertEqual(payload["manifest"]["archivos"]["omitidos"][0]["motivo"], "no cupo en esta copia")

    def test_no_se_cuelan_archivos_de_otra_clinica(self):
        from apps.common.models import Tenant

        otra = Tenant.objects.create(name="Otra")
        ajeno = Patient.objects.create(tenant=otra, first_name="Luis", last_name="Mora", national_id="9")
        doc = PatientDocument(patient=ajeno, doc_type="radiograph")
        doc.file.save("ajena.png", ContentFile(b"ajena"), save=True)
        rutas = {a["ruta"] for a in self.abrir(con_archivos=True)["archivos"]}
        self.assertEqual(rutas, {self.doc.file.name})

    def test_desde_el_panel(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(reverse("tenant-backup"), {
            "passphrase": FRASE, "passphrase_confirm": FRASE, "incluir_archivos": True,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r["X-Backup-Archivos"], r["X-Backup-Archivos-Omitidos"]), ("1", "0"))
        z = zipfile.ZipFile(io.BytesIO(r.content))
        self.assertIn("Archivos:      1", z.read("COMO-DESCIFRAR.txt").decode("utf-8"))

        # Al abrirla en el panel se dice qué archivos hay, sin su contenido.
        copia = sacar_copia(r.content)
        abierta = self.client.post(reverse("tenant-backup-decrypt"), {
            "file": io.BytesIO(copia), "passphrase": FRASE,
        }, format="multipart")
        self.assertEqual(abierta.status_code, 200, abierta.content)
        self.assertEqual(abierta.data["archivos"], [{"ruta": self.doc.file.name, "bytes": len(RADIOGRAFIA)}])


class ArchivosEnLaTerminal(SimpleTestCase):
    """descifrar.py deja los archivos en una carpeta, y solo dentro de ella."""

    def test_extrae_los_archivos_y_no_escribe_fuera(self):
        contenido = {
            "manifest": {"format": "clinica-backup", "version": 1, "total_records": 0,
                         "generated_at": "2026-10-04T10:00:00-05:00", "tenant": {"name": "X"},
                         "archivos": {"incluidos": 2, "bytes": 3, "omitidos": []}},
            "records": [],
            "archivos": [
                {"ruta": "clinical/radiographs/rx.png", "bytes": 2,
                 "contenido": base64.b64encode(b"rx").decode()},
                {"ruta": "../fuera.txt", "bytes": 1, "contenido": base64.b64encode(b"!").decode()},
            ],
        }
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "trabajo"
            ruta.mkdir()
            (ruta / "copia.clinicabk").write_bytes(
                encrypt(gzip.compress(json.dumps(contenido).encode()), FRASE))
            entorno = {**os.environ, "FRASE_RESPALDO": FRASE}
            entorno.pop("DJANGO_SETTINGS_MODULE", None)
            r = subprocess.run([sys.executable, str(KIT / "descifrar.py"), "copia.clinicabk"],
                               cwd=ruta, env=entorno, capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((ruta / "copia-archivos/clinical/radiographs/rx.png").read_bytes(), b"rx")
            self.assertFalse((Path(d) / "fuera.txt").exists())
            self.assertFalse((ruta / "fuera.txt").exists())
            # El JSON queda sin el base64: los archivos ya están en la carpeta.
            escrito = json.loads((ruta / "copia.json").read_text("utf-8"))
            self.assertNotIn("contenido", escrito["archivos"][0])
            self.assertIn("archivos → copia-archivos/", r.stdout)
