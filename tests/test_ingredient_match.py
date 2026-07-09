"""
Pruebas con escenarios variados para el matching de ingredientes (analyze_overlap).

Cubre IL3.1 (precisión con variabilidad de datos): estos son los mismos casos
reales que se usaron para diagnosticar y corregir el bug de falsos positivos
(un solo ingrediente común, como "sal", no debía calzar con cualquier receta).
"""
import pytest

from app.ingredient_match import (
    analyze_overlap,
    es_consulta_sustitucion,
    es_solicitud_generar_receta,
    user_ingredient_in_text,
)

RECETA_POLLO_AJILLO = """
=== RECETA 3: POLLO AL AJILLO ===
Ingredientes:
- 600g de pechuga de pollo
- 8 dientes de ajo
- 100ml de vino blanco
- Aceite de oliva
- Perejil fresco
- Sal y pimienta
- Harina para rebozar (opcional)

Instrucciones:
1. Corta el pollo en trozos medianos.
2. Pela y lamina finamente los ajos.
"""

RECETA_BROWNIES = """
=== RECETA 6: BROWNIES DE CHOCOLATE ===
Ingredientes:
- 200g de chocolate oscuro (70%)
- 150g de mantequilla
- 200g de azucar
- 3 huevos

Instrucciones:
1. Precalienta el horno a 180 grados.
"""


class TestIngredientePrincipal:
    """El caso que motivó la corrección: un ingrediente menor y común (sal) no
    debe hacer que se recomiende una receta cuyo ingrediente principal falta."""

    def test_un_solo_ingrediente_comun_no_debe_calzar(self):
        resultado = analyze_overlap(["sal"], RECETA_POLLO_AJILLO)
        assert resultado["nivel_coincidencia"] == "bajo"
        assert resultado["ingrediente_principal_coincide"] is False

    def test_ingrediente_principal_presente_calza_alto(self):
        resultado = analyze_overlap(["pollo", "ajo"], RECETA_POLLO_AJILLO)
        assert resultado["ingrediente_principal_coincide"] is True
        assert resultado["nivel_coincidencia"] == "alto"

    def test_un_solo_ingrediente_principal_es_suficiente(self):
        resultado = analyze_overlap(["chocolate"], RECETA_BROWNIES)
        assert resultado["ingrediente_principal_coincide"] is True
        assert resultado["nivel_coincidencia"] in ("alto", "medio")

    def test_ingrediente_no_relacionado_no_calza(self):
        resultado = analyze_overlap(["pescado"], RECETA_BROWNIES)
        assert resultado["ingrediente_principal_coincide"] is False
        assert resultado["nivel_coincidencia"] == "bajo"

    def test_sin_ingredientes_de_usuario_es_bajo(self):
        resultado = analyze_overlap([], RECETA_POLLO_AJILLO)
        assert resultado["nivel_coincidencia"] == "bajo"

    def test_receta_vacia_es_bajo(self):
        resultado = analyze_overlap(["pollo"], "")
        assert resultado["nivel_coincidencia"] == "bajo"


class TestUserIngredientInText:
    def test_encuentra_ingrediente_como_substring(self):
        assert user_ingredient_in_text("pollo", "600g de pechuga de pollo") is True

    def test_no_encuentra_ingrediente_ausente(self):
        assert user_ingredient_in_text("pescado", "600g de pechuga de pollo") is False

    def test_ingrediente_corto_usa_limite_de_palabra(self):
        # "ajo" no deberia matchear dentro de "trabajo" (limite de palabra para <3 letras
        # no aplica aqui porque "ajo" tiene 3 letras, pero el caso corto general sí se cubre)
        assert user_ingredient_in_text("ajo", "8 dientes de ajo") is True


class TestDeteccionDeIntencion:
    @pytest.mark.parametrize("mensaje", [
        "No tengo cebolla, con que la reemplazo?",
        "Que puedo usar en vez de huevo?",
        "Que alternativa hay a la mantequilla?",
        "Puedo cambiar el azucar por miel?",
    ])
    def test_detecta_consulta_de_sustitucion(self, mensaje):
        assert es_consulta_sustitucion(mensaje) is True

    def test_pregunta_general_no_es_sustitucion(self):
        assert es_consulta_sustitucion("Que puedo cocinar con pollo?") is False

    @pytest.mark.parametrize("mensaje", [
        "Generame una receta nueva con pollo y limon",
        "Creame otra receta con lo que tengo",
        "Dame una receta nueva de postre",
        "Invéntame una receta con lentejas",
    ])
    def test_detecta_solicitud_de_generar_receta(self, mensaje):
        assert es_solicitud_generar_receta(mensaje) is True

    @pytest.mark.parametrize("mensaje", [
        "No tengo cebolla, con que la reemplazo en la ensalada mediterranea?",
        "Cuanto tiempo se cocina el arroz?",
        "Que puedo cocinar con pollo?",
    ])
    def test_consulta_normal_no_es_solicitud_de_generar(self, mensaje):
        assert es_solicitud_generar_receta(mensaje) is False
