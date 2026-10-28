"""
modelo.py

Estructura del CV base. Se valida con Pydantic al cargar el YAML,
así un error de tipeo (una sección mal escrita, una lista vacía)
salta al inicio y no a mitad de generar un CV.
"""

from typing import Optional

from pydantic import BaseModel, Field


class Contacto(BaseModel):
    nombre: str
    email: str
    telefono: Optional[str] = None
    ubicacion: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None


class Experiencia(BaseModel):
    empresa: str
    cargo: str
    ubicacion: Optional[str] = None
    inicio: str
    fin: str  # "Actualidad" si sigue vigente
    logros: list[str] = Field(min_length=1)
    stack: list[str] = []


class Proyecto(BaseModel):
    nombre: str
    contexto: Optional[str] = None  # ej. "IAthon Construye Perú", "curso X"
    fecha: Optional[str] = None
    logros: list[str] = Field(min_length=1)
    stack: list[str] = []


class Habilidad(BaseModel):
    nombre: str
    nivel: Optional[str] = None  # texto libre: "Intermedio", "Avanzado"...


class GrupoHabilidades(BaseModel):
    grupo: str
    items: list[Habilidad] = Field(min_length=1)


class Educacion(BaseModel):
    titulo: str
    institucion: str
    inicio: Optional[str] = None
    fin: Optional[str] = None


class Logro(BaseModel):
    titulo: str
    descripcion: Optional[str] = None


class Certificado(BaseModel):
    nombre: str
    emisor: str


class Idioma(BaseModel):
    idioma: str
    nivel: str


class CVBase(BaseModel):
    contacto: Contacto
    perfil: str
    experiencia: list[Experiencia] = []
    proyectos: list[Proyecto] = []
    habilidades: list[GrupoHabilidades] = []
    educacion: list[Educacion] = []
    logros: list[Logro] = []
    certificados: list[Certificado] = []
    idiomas: list[Idioma] = []
    competencias: list[str] = []

    def skills_con_formato(self) -> list[str]:
        """
        Las mismas skills que skills_declaradas, pero con su escritura
        original ("Power BI", no "power bi"), sin duplicados. Es lo que
        se le muestra a Pluma, para que no copie las minúsculas.
        """
        nombres = [h.nombre for g in self.habilidades for h in g.items]
        nombres += [s for p in self.proyectos for s in p.stack]
        nombres += [s for e in self.experiencia for s in e.stack]
        vistas: dict[str, str] = {}
        for n in nombres:
            vistas.setdefault(n.strip().lower(), n.strip())
        return sorted(vistas.values(), key=str.lower)

    def skills_declaradas(self) -> set[str]:
        """
        Todo lo que el CV dice que sabes: habilidades, stacks de
        proyectos y experiencias. Normalizado a minúsculas para
        comparar. Es la lista blanca que usará el validador de Pluma.
        """
        nombres = [h.nombre for g in self.habilidades for h in g.items]
        nombres += [s for p in self.proyectos for s in p.stack]
        nombres += [s for e in self.experiencia for s in e.stack]
        return {n.strip().lower() for n in nombres if n.strip()}
