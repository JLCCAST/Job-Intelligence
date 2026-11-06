import type { EventoAgente } from "./agentes";

// Cliente de la API de Python (/api). Todos los tipos reflejan lo que
// devuelven los endpoints de app/api.py.

export type Oferta = {
  job_id: number;
  puesto: string;
  empresa: string;
  fuente: string;
  estado: string;
  match_score: number | null;
  area: string | null;
  fecha_registro: string;
  url: string | null;
};

export type Recordatorio = { job_id: number; puesto: string; empresa: string; dias: number };

export type Inicio = {
  nombre: string | null;
  ofertas: Oferta[];
  resumen: { nuevas: Oferta[]; recordatorios: Recordatorio[] };
  por_revisar: number;
};

export type HistorialEstado = { fecha: string; estado: string; nota: string | null };

export type VersionCV = {
  job_id: number;
  version: number;
  fecha: string;
  ruta_cv: string;
  ruta_brechas: string;
  usa_texto_de_pluma: boolean;
  enviado: boolean;
  fecha_envio: string | null;
};

export type Tecnologia = {
  name: string;
  category: string;
  requirement_type: "required" | "preferred";
  level: string;
  confidence: number;
  evidence_text: string;
};

export type ResultadoAnalisis = {
  source: string;
  extraction_status: "success" | "partial" | "failed";
  registration_status: "saved" | "duplicate" | "offer_closed" | "not_attempted";
  error_detail: string | null;
  job_id: number | null;
  match_score: number | null;
  cumple_ingles: boolean | null;
  tecnologias_faltantes: string[] | null;
  requisitos_bajo_nivel: string[] | null;
  tecnologias_para_revisar: string[] | null;
  extraction: {
    job_title: string;
    company_name: string;
    area: string;
    english_level: string;
    technologies: Tecnologia[];
  } | null;
};

export type Pregunta = { tecnologia: string; requirement_type: string; texto: string };

export type Diferencia = { tipo: "igual" | "quitado" | "agregado"; texto: string };

/** Un cambio de la IA en tu CV, explicado por Notario (o con motivo automático). */
export type CambioCV = {
  id: string;
  seccion: "perfil" | "experiencia" | "proyectos";
  item: string;
  original: string;
  nuevo: string;
  diferencias: Diferencia[];
  similitud: number; // 0 a 1: si es baja, se muestra "antes / ahora"
  motivo: string;
  motivo_de: "notario" | "calculado";
  requisitos: string[];
  atencion: string | null;
  alerta: string | null;
};

export type FlujoCV = {
  thread_id: string;
  esperando_respuestas: boolean;
  preguntas: Pregunta[];
  esperando_revision: boolean;
  cambios: CambioCV[];
  estructura: string[];
  notario_error: string | null;
  ruta_cv: string | null;
  ruta_brechas: string | null;
  usa_texto_de_pluma: boolean;
  avisos: string[];
  rechazados: string[];
};

export type Respuesta = {
  tecnologia: string;
  la_tengo: boolean;
  nivel?: "basico" | "intermedio" | "avanzado";
  donde?: string;
  detalle?: string;
};

export type Perfil = {
  habilidades: { tecnologia: string; categoria: string; nivel: string; meses_experiencia: number | null; evidencia: string | null }[];
  cv: { nombre: string; perfil: string; experiencias: number; proyectos: { nombre: string; logros: string[]; stack: string[] }[]; habilidades: number } | null;
  respuestas: Respuesta[];
};

/** El CV base completo (data/cv_base.yaml), tal como lo valida app/cv/modelo.py. */
export type CVBase = {
  contacto: Record<string, string | null | undefined>;
  perfil: string;
  experiencia: { empresa: string; cargo: string; ubicacion?: string | null; inicio: string; fin: string; logros: string[]; stack: string[] }[];
  proyectos: { nombre: string; contexto?: string | null; fecha?: string | null; logros: string[]; stack: string[] }[];
  habilidades: { grupo: string; items: { nombre: string; nivel?: string | null }[] }[];
  educacion: unknown[];
  logros: unknown[];
  certificados: { nombre: string; emisor: string }[];
  idiomas: unknown[];
  competencias: string[];
};

export type Prioridad = {
  tecnologia: string;
  categoria: string;
  ofertas: number;
  obligatoria_en: number;
  demanda: number;
  distancia: number;
  estado: string;
  tendencia: number;
  tendencia_txt: string;
  prioridad: number;
};

export type PlanEstudio = {
  generado: string;
  plan: {
    resumen: string;
    items: { tecnologia: string; por_que: string; que_aprender: string[]; proyecto: string; semanas: number }[];
  };
};

export type Brujula = { total_ofertas: number; prioridades: Prioridad[]; plan: PlanEstudio | null };

export type Demanda = {
  tecnologia: string;
  categoria: string;
  obligatoria: number;
  deseable: number;
  total: number;
  la_tengo: boolean;
};

export type ResultadoSabueso = {
  encontradas: number;
  fuera_de_filtro: number;
  ya_registradas: number;
  registradas: { job_id: number; puesto: string }[];
  descartadas: string[];
  pendientes_por_tope: number;
  errores: string[];
};

export class ErrorApi extends Error {}

async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const r = await fetch(`/api${ruta}`, {
    headers: { "Content-Type": "application/json" },
    ...opciones,
  });
  if (!r.ok) {
    let mensaje = `Error ${r.status}`;
    try {
      const cuerpo = await r.json();
      if (typeof cuerpo.detail === "string") mensaje = cuerpo.detail;
      else if (Array.isArray(cuerpo.detail)) mensaje = "Revisa los datos del formulario.";
    } catch {
      /* respuesta sin JSON */
    }
    throw new ErrorApi(mensaje);
  }
  return r.json() as Promise<T>;
}

const post = <T>(ruta: string, cuerpo?: unknown) =>
  pedir<T>(ruta, { method: "POST", body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) });

export const api = {
  inicio: () => pedir<Inicio>("/inicio"),
  ofertas: () => pedir<Oferta[]>("/ofertas"),
  estados: () => pedir<string[]>("/estados"),
  cambiarEstado: (jobId: number, estado: string, nota?: string) =>
    post<{ ok: boolean }>(`/ofertas/${jobId}/estado`, { estado, nota }),
  historial: (jobId: number) => pedir<HistorialEstado[]>(`/ofertas/${jobId}/historial`),
  versionesCV: (jobId: number) => pedir<VersionCV[]>(`/ofertas/${jobId}/cvs`),
  analizar: (texto?: string, url?: string) => post<ResultadoAnalisis>("/analizar", { texto, url }),
  buscarOfertas: () => post<ResultadoSabueso>("/sabueso/buscar"),
  pendiente: (id: string) => pedir<{ url: string; texto: string }>(`/pendientes/${id}`),
  iniciarCV: (jobId: number) => post<FlujoCV>(`/cv/${jobId}/iniciar`),
  responder: (threadId: string, respuestas: Respuesta[]) =>
    post<FlujoCV>(`/cv/flujos/${threadId}/responder`, respuestas),
  perfil: () => pedir<Perfil>("/perfil"),
  cvBase: () => pedir<CVBase>("/cv/base"),
  guardarCvBase: (cv: CVBase) =>
    pedir<{ ok: boolean; habilidades: number }>("/cv/base", { method: "PUT", body: JSON.stringify(cv) }),
  guardarHabilidad: (h: { nombre: string; categoria: string; nivel: string; meses_experiencia?: number; evidencia: string }) =>
    post<{ ok: boolean }>("/perfil/habilidades", h),
  catalogoRevision: () => pedir<{ technology_id: number; tecnologia: string; categoria: string; ofertas: number }[]>("/catalogo/revision"),
  aprobar: (id: number) => post<{ ok: boolean }>(`/catalogo/${id}/aprobar`),
  analisis: () => pedir<{ ofertas: number; demanda: Demanda[] }>("/analisis"),
  brujula: () => pedir<Brujula>("/brujula"),
  generarPlan: () => post<{ plan: PlanEstudio | null; error: string | null }>("/brujula/plan"),
  informeBrujula: () => post<{ ruta: string }>("/brujula/informe"),
};

export const urlArchivo = (ruta: string) => `/api/archivos?ruta=${encodeURIComponent(ruta)}`;

// ---------- Transmisión en vivo de los agentes (Server-Sent Events) ----------


/**
 * POST a un endpoint /api/vivo/... y va entregando cada evento de agente
 * a `alEvento` mientras llega. Devuelve el resultado final del flujo.
 */
export async function transmitir<T>(ruta: string, cuerpo: unknown, alEvento: (ev: EventoAgente) => void): Promise<T> {
  const r = await fetch(`/api/vivo${ruta}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
  if (!r.ok || !r.body) {
    let mensaje = `Error ${r.status}`;
    try {
      const c = await r.json();
      if (typeof c.detail === "string") mensaje = c.detail;
    } catch {
      /* sin JSON */
    }
    throw new ErrorApi(mensaje);
  }
  const lector = r.body.getReader();
  const decodificador = new TextDecoder();
  let pendiente = "";
  let resultado: T | undefined;
  for (;;) {
    const { done, value } = await lector.read();
    if (done) break;
    pendiente += decodificador.decode(value, { stream: true });
    let corte: number;
    while ((corte = pendiente.indexOf("\n\n")) >= 0) {
      const bloque = pendiente.slice(0, corte);
      pendiente = pendiente.slice(corte + 2);
      if (!bloque.startsWith("data: ")) continue;
      const ev = JSON.parse(bloque.slice(6));
      if (ev.tipo === "resultado") resultado = ev.datos as T;
      else if (ev.tipo === "error") throw new ErrorApi(ev.mensaje);
      else alEvento(ev as EventoAgente);
    }
  }
  if (resultado === undefined) throw new ErrorApi("La transmisión terminó sin resultado.");
  return resultado;
}

export const vivo = {
  analizar: (alEvento: (ev: EventoAgente) => void, texto?: string, url?: string) =>
    transmitir<ResultadoAnalisis>("/analizar", { texto, url }, alEvento),
  iniciarCV: (alEvento: (ev: EventoAgente) => void, jobId: number) =>
    transmitir<FlujoCV>(`/cv/${jobId}/iniciar`, undefined, alEvento),
  responder: (alEvento: (ev: EventoAgente) => void, threadId: string, respuestas: Respuesta[]) =>
    transmitir<FlujoCV>(`/cv/flujos/${threadId}/responder`, respuestas, alEvento),
  revisar: (alEvento: (ev: EventoAgente) => void, threadId: string, rechazados: string[]) =>
    transmitir<FlujoCV>(`/cv/flujos/${threadId}/revisar`, { rechazados }, alEvento),
};

export type AgenteInfo = {
  id: string; nombre: string; rol: string; tarea: string; gemini: boolean; flujo: string; modelos: string[];
};
export type Actividad = { fecha: string; agente: string; estado: string; resumen: string; flujo: string };

export const obtenerAgentes = () => pedir<{ agentes: AgenteInfo[]; actividad: Actividad[] }>("/agentes");
