"""
Fuentes de ofertas para Sabueso. Cada fuente es un módulo con una
función `buscar(consulta) -> list[OfertaEncontrada]`.

Solo entran fuentes que PERMITEN el acceso automático (API pública
o términos que lo autorizan). Revisado el 2026-10-23:

    Get on Board  -> API pública documentada, sin clave. Incluida.
    Computrabajo  -> bloquea el acceso automático (403). Excluida.
    Bumeran       -> SPA, sin API pública. Excluida (texto pegado a mano).
    LinkedIn      -> sus términos prohíben el scraping. Excluida.
    Indeed        -> sus términos prohíben el scraping. Excluida.

Para esas, el camino sigue siendo pegar el texto en "Analizar oferta".
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OfertaEncontrada:
    fuente: str
    url: str
    titulo: str
    empresa: Optional[str]
    paises: list[str] = field(default_factory=list)
    remoto: bool = False
    modalidad: Optional[str] = None
    salario_min: Optional[int] = None
    salario_max: Optional[int] = None
    texto: str = ""  # descripción completa en texto plano, lista para Lupa
