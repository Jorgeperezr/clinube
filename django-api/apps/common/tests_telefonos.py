from django.test import SimpleTestCase

from apps.common.telefonos import normalizar_telefono


class NormalizarTelefonoTests(SimpleTestCase):
    def test_como_lo_dicta_el_paciente(self):
        for escrito in ("0991234567", "099 123 4567", "099-123-4567", "+593 99 123 4567",
                        "593991234567", "00593991234567", "991234567"):
            self.assertEqual(normalizar_telefono(escrito), "+593991234567", escrito)

    def test_otro_pais_se_respeta(self):
        self.assertEqual(normalizar_telefono("+34 612 34 56 78"), "+34612345678")

    def test_lo_que_no_es_un_telefono(self):
        for malo in ("", None, "abc", "0999", "+1234567890123456"):
            self.assertEqual(normalizar_telefono(malo), "", malo)
