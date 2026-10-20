"""Pruebas criptográficas para parámetros PKCE según RFC 7636."""

import unittest

from siget_desktop.auth.pkce import (
    PkceContext,
    generar_code_challenge,
    generar_code_verifier,
    generar_state,
)


class PkceTests(unittest.TestCase):
    def test_longitud_code_verifier(self):
        v = generar_code_verifier(64)
        self.assertEqual(len(v), 64)
        self.assertTrue(v.replace("-", "").replace("_", "").isalnum())

    def test_longitud_invalida_rechazada(self):
        with self.assertRaises(ValueError):
            generar_code_verifier(40)
        with self.assertRaises(ValueError):
            generar_code_verifier(130)

    def test_calculo_code_challenge_s256_vector_rfc7636(self):
        # Vector de prueba de RFC 7636 sección 4.1 y anexo B
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        challenge_esperado = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        resultado = generar_code_challenge(verifier)
        self.assertEqual(resultado, challenge_esperado)

    def test_code_challenge_sin_padding(self):
        verifier = generar_code_verifier(64)
        challenge = generar_code_challenge(verifier)
        self.assertNotIn("=", challenge)
        self.assertNotIn("+", challenge)
        self.assertNotIn("/", challenge)

    def test_unicidad_state(self):
        states = {generar_state() for _ in range(100)}
        self.assertEqual(len(states), 100)

    def test_creacion_contexto_pkce(self):
        ctx = PkceContext.create()
        self.assertEqual(ctx.challenge_method, "S256")
        self.assertTrue(len(ctx.verifier) >= 43)
        self.assertTrue(len(ctx.challenge) > 0)
        self.assertTrue(len(ctx.state) > 0)


if __name__ == "__main__":
    unittest.main()
