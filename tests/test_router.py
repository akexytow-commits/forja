"""MOD-010: tabla de resolución determinista (TST-002, TST-006)."""
import pytest

from backend.router import RouterError, resolver

REGISTRO = {
    "pequeno-general": {"alias": "pequeno-general", "tier": "pequeno", "etiqueta": "qwen3:4b", "thinking": 1},
    "pequeno-codigo": {"alias": "pequeno-codigo", "tier": "pequeno", "etiqueta": "qwen2.5-coder:3b", "thinking": 0},
    "grande-general": {"alias": "grande-general", "tier": "grande", "etiqueta": "qwen3:8b", "thinking": 1},
    "grande-codigo": {"alias": "grande-codigo", "tier": "grande", "etiqueta": "qwen2.5-coder:7b", "thinking": 0},
    "nube-frontera": {"alias": "nube-frontera", "tier": "nube", "etiqueta": "", "thinking": 0},
}


def test_tst002_scripts_pequeno_medio():
    plan = resolver("scripts", "pequeno", "medio", 0, REGISTRO)
    assert plan.alias == "pequeno-codigo"
    assert plan.etiqueta_ollama == "qwen2.5-coder:3b"
    assert plan.params["num_ctx"] == 8192


@pytest.mark.parametrize("modo", ["seguridad", "tareas"])
def test_tst006_extra_activa_thinking_high_en_qwen3(modo):
    plan = resolver(modo, "pequeno", "extra", 0, REGISTRO)
    assert plan.thinking_nativo
    assert plan.params["enable_thinking"] is True
    assert plan.params["reasoning_effort"] == "high"
    assert plan.params["num_predict"] == 3072      # doc 04 rev. 8: thinking + respuesta caben en CPU
    assert plan.params["temperatura"] == 0.7


def test_bajo_desactiva_thinking():
    plan = resolver("tareas", "grande", "bajo", 0, REGISTRO)
    assert plan.params["enable_thinking"] is False
    assert plan.params["num_predict"] == 768       # nunca < 768 con qwen3 sin thinking


def test_coder_emula_esfuerzo_por_prompt():
    bajo = resolver("scripts", "pequeno", "bajo", 0, REGISTRO)
    extra = resolver("scripts", "grande", "extra", 0, REGISTRO)
    assert not extra.thinking_nativo and "enable_thinking" not in extra.params
    assert "<plan>" in extra.system_prompt and "<plan>" not in bajo.system_prompt
    assert extra.params["temperatura"] == 0.6 and bajo.params["temperatura"] == 0.2


def test_grande_usa_menos_contexto_y_respeta_tope():
    assert resolver("scripts", "grande", "medio", 0, REGISTRO).params["num_ctx"] == 4096
    assert resolver("scripts", "grande", "medio", 50_000, REGISTRO).params["num_ctx"] == 8192
    assert resolver("scripts", "pequeno", "medio", 9_000, REGISTRO).params["num_ctx"] == 11264  # 9000 + 1024 + 256 → múltiplo de 1024


def test_prompt_incluye_modelo_tier_y_espanol():
    plan = resolver("scripts", "pequeno", "medio", 0, REGISTRO)
    assert "qwen2.5-coder:3b" in plan.system_prompt
    assert "español" in plan.system_prompt


def test_requiere_carga():
    assert resolver("scripts", "pequeno", "bajo", 0, REGISTRO, ["qwen3:4b"]).requiere_carga
    assert not resolver("scripts", "pequeno", "bajo", 0, REGISTRO, ["qwen2.5-coder:3b"]).requiere_carga


@pytest.mark.parametrize("args", [("hackeo", "pequeno", "bajo"), ("scripts", "enorme", "bajo"),
                                  ("scripts", "pequeno", "maximo")])
def test_valores_invalidos(args):
    with pytest.raises(RouterError):
        resolver(*args, 0, REGISTRO)
