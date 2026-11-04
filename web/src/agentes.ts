import {
  Archive, Bell, Compass, MessageCircleQuestion, PenLine, Printer, Radar, Scale, Search, ShieldCheck, Workflow,
  type LucideIcon,
} from "lucide-react";

// Identidad visual de cada agente. Los ids coinciden con app/agents/eventos.py.
export const AGENTE: Record<string, { nombre: string; rol: string; icono: LucideIcon; color: string }> = {
  batuta: { nombre: "Batuta", rol: "Orquestador", icono: Workflow, color: "#7c5cd6" },
  sabueso: { nombre: "Sabueso", rol: "Buscador", icono: Radar, color: "#0f8f8a" },
  lupa: { nombre: "Lupa", rol: "Extractor", icono: Search, color: "#2a78d6" },
  archivero: { nombre: "Archivero", rol: "Normalizador", icono: Archive, color: "#8a6a3b" },
  balanza: { nombre: "Balanza", rol: "Evaluador", icono: Scale, color: "#1baf7a" },
  pregunton: { nombre: "Preguntón", rol: "Entrevistador", icono: MessageCircleQuestion, color: "#e0892b" },
  pluma: { nombre: "Pluma", rol: "Redactor", icono: PenLine, color: "#d4537e" },
  validador: { nombre: "Validador", rol: "Control de calidad", icono: ShieldCheck, color: "#3b6d11" },
  imprenta: { nombre: "Imprenta", rol: "Documentador", icono: Printer, color: "#546078" },
  centinela: { nombre: "Centinela", rol: "Seguimiento", icono: Bell, color: "#b3261e" },
  brujula: { nombre: "Brújula", rol: "Mentor", icono: Compass, color: "#eb6834" },
};

export type EventoAgente =
  | { tipo: "inicio"; nodo: string; agente: string; accion: string }
  | { tipo: "fin"; nodo: string; agente: string; estado: EstadoPaso; resumen: string; ms: number };

export type EstadoPaso = "trabajando" | "ok" | "detenido" | "pausa" | "rechazo" | "error";

export type Paso = {
  id: number;
  nodo: string;
  agente: string;
  estado: EstadoPaso;
  texto: string;
  ms?: number;
};

/** Agrega un evento a la lista de pasos: "inicio" crea uno, "fin" completa el último abierto de ese nodo. */
export function aplicarEvento(pasos: Paso[], ev: EventoAgente): Paso[] {
  if (ev.tipo === "inicio") {
    return [...pasos, { id: pasos.length, nodo: ev.nodo, agente: ev.agente, estado: "trabajando", texto: ev.accion }];
  }
  const i = pasos.map((p) => p.nodo === ev.nodo && p.estado === "trabajando").lastIndexOf(true);
  if (i < 0) return pasos;
  const copia = [...pasos];
  copia[i] = { ...copia[i], estado: ev.estado, texto: ev.resumen, ms: ev.ms };
  return copia;
}
