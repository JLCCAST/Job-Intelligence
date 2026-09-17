"""
scoring.py

Responsabilidad única: calcular el Match Score de una oferta
comparando lo que pide contra lo que declaraste en `user_skill`.

100% determinístico -- NO interviene el LLM. Gemini ya hizo su
trabajo (extraer los requisitos); decidir qué tan bien calzas es
aritmética sobre dos tablas.

La fórmula:

    Score = Σ(peso × crédito) / Σ(peso) × 100

    peso    = 1.0 si la oferta la pide como 'required'
              0.5 si la pide como 'preferred'
    crédito = 1.0 si la tienes en el nivel pedido o más
              0.7 si la tienes pero en un nivel menor
              0.0 si no la tienes

Dos propiedades importantes de esta forma:

- El denominador lo define la OFERTA, no tu perfil. Por eso saber
  cosas que la oferta no pide NO sube tu score, y por eso un score
  es comparable entre ofertas con distinta cantidad de requisitos.
- Lo que la oferta pide y no tienes no "resta" con una penalización
  aparte: ya baja el score al estar en el denominador sin aportar
  al numerador.

OJO: la fórmula no tiene ninguna defensa contra inflar tu propio
perfil (declarar más habilidades solo puede subir el score). Esa
defensa es humana y vive en el campo `user_skill.evidencia`.
"""

from dataclasses import dataclass, field
from typing import Optional

# --- Parámetros de la fórmula (decididos en la Fase 5) ---

PESO_REQUIRED = 1.0
PESO_PREFERRED = 0.5

CREDITO_NIVEL_SUFICIENTE = 1.0
CREDITO_NIVEL_MENOR = 0.7
CREDITO_NO_LA_TENGO = 0.0

# Orden de niveles, para poder comparar "¿alcanzo lo que piden?".
# 'unspecified' = la oferta no dijo nivel; basta con tener la
# tecnología en cualquier nivel.
ORDEN_NIVEL = {
    "basico": 1,
    "intermedio": 2,
    "avanzado": 3,
}

NIVEL_NO_ESPECIFICADO = {"unspecified", "no_especificado", None, ""}

# El inglés no vive en job_technology sino en la columna
# job.ingles_requerido, pero pesa como un requisito obligatorio más.
NOMBRE_TECNOLOGIA_INGLES = "inglés"
PESO_INGLES = 1.0


@dataclass
class ItemScore:
    """Cómo aportó una tecnología concreta al score."""
    nombre: str
    requirement_type: str
    nivel_pedido: Optional[str]
    nivel_usuario: Optional[str]
    peso: float
    credito: float

    @property
    def aporte(self) -> float:
        return self.peso * self.credito

    @property
    def la_tengo(self) -> bool:
        return self.nivel_usuario is not None


@dataclass
class MatchScoreResult:
    """
    `score` es None cuando la oferta no pide NADA evaluable (ni
    tecnologías ni inglés). Eso NO es lo mismo que 0.0: un 0.0
    significa "pide cosas y no cubro ninguna". Devolver 0.0 acá
    haría que ofertas sin requisitos extraídos se vean como el peor
    match posible, cuando en realidad no hay información.
    """
    score: Optional[float]
    items: list[ItemScore] = field(default_factory=list)
    cumple_ingles: Optional[bool] = None   # None = la oferta no pidió inglés
    faltantes: list[str] = field(default_factory=list)
    cubiertas: list[str] = field(default_factory=list)

    # Requisitos OBLIGATORIOS que tienes, pero por debajo del nivel
    # pedido. Se reportan aparte por la misma razón que cumple_ingles:
    # el promedio los suaviza (crédito 0.7) y los esconde. Una oferta
    # puede dar 92% y aun así pedirte avanzado en su herramienta
    # central, donde estás en intermedio.
    # Solo 'required': que un "deseable" te quede grande no es un
    # problema que debas ver destacado.
    requisitos_bajo_nivel: list[str] = field(default_factory=list)


def _peso_por_tipo(requirement_type: str) -> float:
    return PESO_REQUIRED if requirement_type == "required" else PESO_PREFERRED


def calcular_credito(
    nivel_pedido: Optional[str],
    nivel_usuario: Optional[str],
) -> float:
    """
    Cuánto crédito (0 a 1) se lleva una tecnología.

    Función pura: es el corazón de la fórmula y se testea sola.
    """
    if nivel_usuario is None:
        return CREDITO_NO_LA_TENGO

    # La oferta no especificó nivel -> basta con tenerla.
    if nivel_pedido in NIVEL_NO_ESPECIFICADO:
        return CREDITO_NIVEL_SUFICIENTE

    pedido = ORDEN_NIVEL.get(nivel_pedido)
    mio = ORDEN_NIVEL.get(nivel_usuario)

    # Nivel no reconocido de cualquiera de los dos lados: se es
    # generoso (la tiene), pero no se inventa una comparación.
    if pedido is None or mio is None:
        return CREDITO_NIVEL_SUFICIENTE

    return CREDITO_NIVEL_SUFICIENTE if mio >= pedido else CREDITO_NIVEL_MENOR


def calcular_match_score(
    requisitos: list[dict],
    mis_niveles: dict[int, str],
    ingles_requerido: Optional[str] = None,
    mi_nivel_ingles: Optional[str] = None,
) -> MatchScoreResult:
    """
    Calcula el score de UNA oferta.

    `requisitos`: lo que pide la oferta. Cada dict:
        {technology_id, nombre, requirement_type, level}
    `mis_niveles`: {technology_id: level} sacado de user_skill.
    `ingles_requerido`: valor de job.ingles_requerido.
    `mi_nivel_ingles`: tu nivel declarado de inglés, si lo declaraste.

    Recibe datos ya cargados, no consulta la BD: así la fórmula se
    puede testear sin Supabase.
    """
    items: list[ItemScore] = []
    faltantes: list[str] = []
    cubiertas: list[str] = []
    bajo_nivel: list[str] = []

    for req in requisitos:
        nivel_usuario = mis_niveles.get(req["technology_id"])
        peso = _peso_por_tipo(req["requirement_type"])
        credito = calcular_credito(req.get("level"), nivel_usuario)

        items.append(
            ItemScore(
                nombre=req["nombre"],
                requirement_type=req["requirement_type"],
                nivel_pedido=req.get("level"),
                nivel_usuario=nivel_usuario,
                peso=peso,
                credito=credito,
            )
        )

        if nivel_usuario is None:
            faltantes.append(req["nombre"])
        else:
            cubiertas.append(req["nombre"])
            if req["requirement_type"] == "required" and credito < CREDITO_NIVEL_SUFICIENTE:
                bajo_nivel.append(req["nombre"])

    # --- Inglés: un ítem obligatorio más, pero solo si la oferta lo pide ---
    cumple_ingles: Optional[bool] = None

    if ingles_requerido not in NIVEL_NO_ESPECIFICADO:
        credito_ingles = calcular_credito(ingles_requerido, mi_nivel_ingles)
        items.append(
            ItemScore(
                nombre="Inglés",
                requirement_type="required",
                nivel_pedido=ingles_requerido,
                nivel_usuario=mi_nivel_ingles,
                peso=PESO_INGLES,
                credito=credito_ingles,
            )
        )

        # El flag es más estricto que el crédito: 0.7 suma al score,
        # pero para el flag "¿cumplo el inglés?" la respuesta es no.
        cumple_ingles = credito_ingles >= CREDITO_NIVEL_SUFICIENTE

        if mi_nivel_ingles is None:
            faltantes.append("Inglés")
        else:
            cubiertas.append("Inglés")

    # --- Score final ---
    peso_total = sum(item.peso for item in items)

    if peso_total == 0:
        # La oferta no pide nada evaluable. No es un 0%, es "no hay
        # información" -- ver el docstring de MatchScoreResult.
        score = None
    else:
        aporte_total = sum(item.aporte for item in items)
        score = round(aporte_total / peso_total * 100, 2)

    return MatchScoreResult(
        score=score,
        items=items,
        cumple_ingles=cumple_ingles,
        faltantes=faltantes,
        cubiertas=cubiertas,
        requisitos_bajo_nivel=bajo_nivel,
    )
