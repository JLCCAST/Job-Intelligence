import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ChevronDown, Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useBlocker } from "react-router";
import { api, type CVBase } from "../api";
import { useAvisos } from "./avisos";
import { Aviso, Boton, Campo, Cargando, Tarjeta, claseCampo, cx } from "./ui";

// Editor del CV base (data/cv_base.yaml). Trabaja sobre un borrador en
// texto plano (un logro por línea, stack separado por comas) y solo
// escribe el archivo al presionar Guardar. La API valida con Pydantic y
// deja un respaldo de la versión anterior.

type ProyectoB = { id: number; nombre: string; contexto: string; fecha: string; logros: string; stack: string };
type ExperienciaB = { id: number; empresa: string; cargo: string; ubicacion: string; inicio: string; fin: string; logros: string; stack: string };
type GrupoB = { id: number; grupo: string; items: string };
type Borrador = { perfil: string; proyectos: ProyectoB[]; experiencia: ExperienciaB[]; habilidades: GrupoB[]; certificados: string };

let siguienteId = 1;
const nuevoId = () => siguienteId++;

const lineas = (t: string) => t.split("\n").map((l) => l.replace(/^\s*[-•●]\s*/, "").trim()).filter(Boolean);
const comas = (t: string) => t.split(",").map((s) => s.trim()).filter(Boolean);
const opcional = (t: string) => t.trim() || null;

/** "Power BI (Intermedio)" <-> {nombre: "Power BI", nivel: "Intermedio"} */
const itemATexto = (h: { nombre: string; nivel?: string | null }) => (h.nivel ? `${h.nombre} (${h.nivel})` : h.nombre);
function textoAItem(t: string) {
  const m = t.match(/^(.*?)\s*\(([^()]+)\)$/);
  return m ? { nombre: m[1].trim(), nivel: m[2].trim() } : { nombre: t, nivel: null };
}

function aBorrador(cv: CVBase): Borrador {
  return {
    perfil: cv.perfil,
    proyectos: cv.proyectos.map((p) => ({
      id: nuevoId(), nombre: p.nombre, contexto: p.contexto ?? "", fecha: p.fecha ?? "",
      logros: p.logros.join("\n"), stack: p.stack.join(", "),
    })),
    experiencia: cv.experiencia.map((e) => ({
      id: nuevoId(), empresa: e.empresa, cargo: e.cargo, ubicacion: e.ubicacion ?? "", inicio: e.inicio, fin: e.fin,
      logros: e.logros.join("\n"), stack: e.stack.join(", "),
    })),
    habilidades: cv.habilidades.map((g) => ({ id: nuevoId(), grupo: g.grupo, items: g.items.map(itemATexto).join(", ") })),
    certificados: cv.certificados.map((c) => `${c.nombre} | ${c.emisor}`).join("\n"),
  };
}

function aCV(b: Borrador, original: CVBase): CVBase {
  return {
    ...original, // contacto, educación, idiomas...: se editan en el YAML
    perfil: b.perfil.trim(),
    proyectos: b.proyectos.map((p) => ({
      nombre: p.nombre.trim(), contexto: opcional(p.contexto), fecha: opcional(p.fecha),
      logros: lineas(p.logros), stack: comas(p.stack),
    })),
    experiencia: b.experiencia.map((e) => ({
      empresa: e.empresa.trim(), cargo: e.cargo.trim(), ubicacion: opcional(e.ubicacion),
      inicio: e.inicio.trim(), fin: e.fin.trim(), logros: lineas(e.logros), stack: comas(e.stack),
    })),
    habilidades: b.habilidades.map((g) => ({ grupo: g.grupo.trim(), items: comas(g.items).map(textoAItem) })),
    certificados: lineas(b.certificados).map((l) => {
      const [nombre, ...resto] = l.split("|");
      return { nombre: nombre.trim(), emisor: resto.join("|").trim() };
    }),
  };
}

function errores(cv: CVBase): string[] {
  const e: string[] = [];
  if (!cv.perfil) e.push("El perfil profesional está vacío.");
  cv.proyectos.forEach((p, i) => {
    const quien = p.nombre || `El proyecto ${i + 1}`;
    if (!p.nombre) e.push(`El proyecto ${i + 1} no tiene nombre.`);
    if (!p.logros.length) e.push(`${quien} necesita al menos un logro.`);
  });
  cv.experiencia.forEach((x, i) => {
    const quien = x.empresa || `La experiencia ${i + 1}`;
    if (!x.empresa || !x.cargo) e.push(`${quien}: falta la empresa o el cargo.`);
    if (!x.inicio || !x.fin) e.push(`${quien}: falta la fecha de inicio o de fin (usa "actualidad" si sigue).`);
    if (!x.logros.length) e.push(`${quien} necesita al menos un logro.`);
  });
  cv.habilidades.forEach((g, i) => {
    if (!g.grupo) e.push(`El grupo de habilidades ${i + 1} no tiene nombre.`);
    if (!g.items.length) e.push(`El grupo "${g.grupo || i + 1}" no tiene habilidades.`);
  });
  cv.certificados.forEach((c) => { if (!c.emisor) e.push(`Al certificado "${c.nombre}" le falta el emisor (Nombre | Emisor).`); });
  return e;
}

/** Todo lo que Pluma tiene permitido mencionar (igual que skills_declaradas en Python). */
function declaradas(cv: CVBase) {
  return new Map(
    [...cv.habilidades.flatMap((g) => g.items.map((h) => h.nombre)), ...cv.proyectos.flatMap((p) => p.stack), ...cv.experiencia.flatMap((x) => x.stack)]
      .map((n) => [n.trim().toLowerCase(), n.trim()] as const),
  );
}

export default function EditorCV() {
  const { data: original, isLoading, error } = useQuery({ queryKey: ["cvBase"], queryFn: api.cvBase, retry: false });
  const [b, setB] = useState<Borrador | null>(null);
  const qc = useQueryClient();
  const avisar = useAvisos();

  useEffect(() => { if (original && !b) setB(aBorrador(original)); }, [original, b]);

  const cv = useMemo(() => (b && original ? aCV(b, original) : null), [b, original]);
  // Se compara contra el original pasado por el mismo ida y vuelta, para no marcar cambios que no hiciste.
  const referencia = useMemo(() => (original ? JSON.stringify(aCV(aBorrador(original), original)) : ""), [original]);
  const sucio = !!cv && JSON.stringify(cv) !== referencia;
  const problemas = cv ? errores(cv) : [];

  // Avisa antes de irte a otra página de la app con cambios sin guardar...
  const bloqueo = useBlocker(sucio);
  useEffect(() => {
    if (bloqueo.state !== "blocked") return;
    if (confirm("Tienes cambios sin guardar en tu CV base. ¿Salir y perderlos?")) bloqueo.proceed();
    else bloqueo.reset();
  }, [bloqueo]);

  // ...y antes de cerrar o recargar la pestaña del navegador.
  useEffect(() => {
    if (!sucio) return;
    const alSalir = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", alSalir);
    return () => { window.removeEventListener("beforeunload", alSalir); };
  }, [sucio]);

  const guardar = useMutation({
    mutationFn: () => api.guardarCvBase(cv!),
    onSuccess: () => {
      const antes = declaradas(original!);
      const nuevas = [...declaradas(cv!)].filter(([k]) => !antes.has(k)).map(([, v]) => v);
      avisar(nuevas.length ? `CV base guardado. Pluma ahora también puede usar: ${nuevas.join(", ")}.` : "CV base guardado.");
      qc.setQueryData(["cvBase"], cv);
      qc.invalidateQueries({ queryKey: ["perfil"] });
      setB(aBorrador(cv!));
    },
    onError: (e) => avisar(e.message, true),
  });

  if (isLoading) return <Cargando />;
  if (error || !original) return <Aviso tono="bad" titulo="No se pudo cargar el CV base">{error?.message}</Aviso>;
  if (!b || !cv) return <Cargando />;

  const cambiar = (parcial: Partial<Borrador>) => setB({ ...b, ...parcial });
  function lista<K extends "proyectos" | "experiencia" | "habilidades">(clave: K) {
    const items = b![clave] as Borrador[K];
    return {
      editar: (id: number, cambio: Partial<Borrador[K][number]>) =>
        cambiar({ [clave]: items.map((x) => (x.id === id ? { ...x, ...cambio } : x)) } as Partial<Borrador>),
      quitar: (id: number) => cambiar({ [clave]: items.filter((x) => x.id !== id) } as Partial<Borrador>),
      mover: (id: number, paso: -1 | 1) => {
        const i = items.findIndex((x) => x.id === id);
        const j = i + paso;
        if (j < 0 || j >= items.length) return;
        const copia = [...items];
        [copia[i], copia[j]] = [copia[j], copia[i]];
        cambiar({ [clave]: copia } as Partial<Borrador>);
      },
    };
  }
  const proyectos = lista("proyectos");
  const experiencia = lista("experiencia");
  const habilidades = lista("habilidades");

  return (
    <div className="flex flex-col gap-6">
      {/* Barra de guardado: siempre visible mientras editas */}
      <div className="sticky top-0 z-10 -mx-1 flex flex-wrap items-center justify-between gap-3 border-b border-line bg-bg px-1 py-3">
        <p className="text-sm text-ink-2">
          {sucio ? <span className="font-medium text-warn">Tienes cambios sin guardar.</span> : "Pluma solo puede usar lo que está aquí."}
          {" "}Contacto, educación e idiomas se editan en <code className="font-mono text-xs">data/cv_base.yaml</code>.
        </p>
        <div className="flex gap-2">
          <Boton variante="fantasma" icono={RotateCcw} disabled={!sucio || guardar.isPending} onClick={() => setB(aBorrador(original))}>Descartar</Boton>
          <Boton variante="primario" icono={Save} cargando={guardar.isPending} disabled={!sucio || problemas.length > 0} onClick={() => guardar.mutate()}>
            Guardar cambios
          </Boton>
        </div>
      </div>

      {sucio && problemas.length > 0 && (
        <Aviso tono="warn" titulo="Corrige esto para poder guardar">
          <ul className="list-disc pl-4">{problemas.map((p) => <li key={p}>{p}</li>)}</ul>
        </Aviso>
      )}

      <Bloque titulo="Perfil profesional" ayuda="3 o 4 líneas: qué estudias, en qué te enfocas, qué has hecho y qué prácticas buscas. Pluma lo adapta a cada oferta.">
        <textarea className={cx(claseCampo, "min-h-28")} value={b.perfil} onChange={(e) => cambiar({ perfil: e.target.value })} />
      </Bloque>

      <Bloque
        titulo={`Proyectos (${b.proyectos.length})`}
        ayuda="Pon todos, aunque no quepan en una hoja: Pluma elige los que mejor encajan con cada oferta. El orden de aquí es el orden de preferencia."
        accion={<Boton icono={Plus} onClick={() => cambiar({ proyectos: [{ id: nuevoId(), nombre: "", contexto: "", fecha: "", logros: "", stack: "" }, ...b.proyectos] })}>Agregar proyecto</Boton>}
      >
        {b.proyectos.map((p, i) => (
          <Item key={p.id} titulo={p.nombre || "Proyecto nuevo"} subtitulo={[p.contexto, p.fecha].filter(Boolean).join(" · ")}
                abierto={!p.nombre} primero={i === 0} ultimo={i === b.proyectos.length - 1}
                onSubir={() => proyectos.mover(p.id, -1)} onBajar={() => proyectos.mover(p.id, 1)} onQuitar={() => proyectos.quitar(p.id)}>
            <Campo etiqueta="Nombre"><input className={claseCampo} value={p.nombre} placeholder="Ej.: Dashboard de ventas – Power BI" onChange={(e) => proyectos.editar(p.id, { nombre: e.target.value })} /></Campo>
            <div className="grid gap-3 sm:grid-cols-2">
              <Campo etiqueta="Contexto (opcional)"><input className={claseCampo} value={p.contexto} placeholder="Proyecto académico, personal, hackathon..." onChange={(e) => proyectos.editar(p.id, { contexto: e.target.value })} /></Campo>
              <Campo etiqueta="Fecha (opcional)"><input className={claseCampo} value={p.fecha} placeholder="Ej.: Dic. 2026" onChange={(e) => proyectos.editar(p.id, { fecha: e.target.value })} /></Campo>
            </div>
            <CampoLogros valor={p.logros} onChange={(v) => proyectos.editar(p.id, { logros: v })} />
            <CampoStack valor={p.stack} onChange={(v) => proyectos.editar(p.id, { stack: v })} />
          </Item>
        ))}
      </Bloque>

      <Bloque
        titulo={`Experiencia laboral (${b.experiencia.length})`}
        accion={<Boton icono={Plus} onClick={() => cambiar({ experiencia: [{ id: nuevoId(), empresa: "", cargo: "", ubicacion: "", inicio: "", fin: "", logros: "", stack: "" }, ...b.experiencia] })}>Agregar experiencia</Boton>}
      >
        {b.experiencia.map((x, i) => (
          <Item key={x.id} titulo={x.empresa ? `${x.empresa} | ${x.cargo}` : "Experiencia nueva"} subtitulo={[x.inicio, x.fin].filter(Boolean).join(" – ")}
                abierto={!x.empresa} primero={i === 0} ultimo={i === b.experiencia.length - 1}
                onSubir={() => experiencia.mover(x.id, -1)} onBajar={() => experiencia.mover(x.id, 1)} onQuitar={() => experiencia.quitar(x.id)}>
            <div className="grid gap-3 sm:grid-cols-2">
              <Campo etiqueta="Empresa"><input className={claseCampo} value={x.empresa} onChange={(e) => experiencia.editar(x.id, { empresa: e.target.value })} /></Campo>
              <Campo etiqueta="Cargo"><input className={claseCampo} value={x.cargo} onChange={(e) => experiencia.editar(x.id, { cargo: e.target.value })} /></Campo>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <Campo etiqueta="Ubicación (opcional)"><input className={claseCampo} value={x.ubicacion} onChange={(e) => experiencia.editar(x.id, { ubicacion: e.target.value })} /></Campo>
              <Campo etiqueta="Inicio"><input className={claseCampo} value={x.inicio} placeholder="Ene. 2025" onChange={(e) => experiencia.editar(x.id, { inicio: e.target.value })} /></Campo>
              <Campo etiqueta="Fin"><input className={claseCampo} value={x.fin} placeholder="actualidad" onChange={(e) => experiencia.editar(x.id, { fin: e.target.value })} /></Campo>
            </div>
            <CampoLogros valor={x.logros} onChange={(v) => experiencia.editar(x.id, { logros: v })} />
            <CampoStack valor={x.stack} onChange={(v) => experiencia.editar(x.id, { stack: v })} />
          </Item>
        ))}
      </Bloque>

      <Bloque
        titulo="Habilidades técnicas"
        ayuda='Separadas por comas. Solo lo que puedes defender en una entrevista; el nivel es opcional y va entre paréntesis: "SQL (Intermedio)".'
        accion={<Boton icono={Plus} onClick={() => cambiar({ habilidades: [...b.habilidades, { id: nuevoId(), grupo: "", items: "" }] })}>Agregar grupo</Boton>}
      >
        <Tarjeta className="flex flex-col gap-3">
          {b.habilidades.map((g, i) => (
            <div key={g.id} className="grid items-start gap-2 sm:grid-cols-[200px_1fr_auto]">
              <input className={cx(claseCampo, "font-medium")} value={g.grupo} placeholder="Nombre del grupo" aria-label="Nombre del grupo" onChange={(e) => habilidades.editar(g.id, { grupo: e.target.value })} />
              <input className={claseCampo} value={g.items} placeholder="SQL, Python, Power BI" aria-label={`Habilidades de ${g.grupo}`} onChange={(e) => habilidades.editar(g.id, { items: e.target.value })} />
              <Acciones primero={i === 0} ultimo={i === b.habilidades.length - 1}
                        onSubir={() => habilidades.mover(g.id, -1)} onBajar={() => habilidades.mover(g.id, 1)} onQuitar={() => habilidades.quitar(g.id)} />
            </div>
          ))}
        </Tarjeta>
      </Bloque>

      <Bloque titulo="Certificaciones" ayuda="Una por línea, con el emisor después de una barra: SQL Completo | midudev">
        <textarea className={cx(claseCampo, "min-h-20 font-mono text-xs")} value={b.certificados} onChange={(e) => cambiar({ certificados: e.target.value })} />
      </Bloque>
    </div>
  );
}

// ---------- Piezas ----------

function Bloque({ titulo, ayuda, accion, children }: { titulo: string; ayuda?: string; accion?: ReactNode; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">{titulo}</h2>
          {ayuda && <p className="mt-0.5 max-w-3xl text-sm text-ink-2">{ayuda}</p>}
        </div>
        {accion}
      </div>
      {children}
    </section>
  );
}

function Item({ titulo, subtitulo, abierto, children, ...acciones }: {
  titulo: string; subtitulo?: string; abierto?: boolean; children: ReactNode;
  primero: boolean; ultimo: boolean; onSubir: () => void; onBajar: () => void; onQuitar: () => void;
}) {
  return (
    <details open={abierto} className="group rounded-md border border-line bg-surface">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-3.5">
        <ChevronDown className="size-4 shrink-0 text-ink-3 transition group-open:rotate-180" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-ink">{titulo}</p>
          {subtitulo && <p className="truncate text-xs text-ink-3">{subtitulo}</p>}
        </div>
        <Acciones {...acciones} />
      </summary>
      <div className="flex flex-col gap-3 border-t border-line px-5 py-4">{children}</div>
    </details>
  );
}

function Acciones({ primero, ultimo, onSubir, onBajar, onQuitar }: {
  primero: boolean; ultimo: boolean; onSubir: () => void; onBajar: () => void; onQuitar: () => void;
}) {
  // preventDefault: que los botones no abran/cierren el <details>.
  const clic = (f: () => void) => (e: React.MouseEvent) => { e.preventDefault(); f(); };
  const base = "rounded p-1.5 text-ink-3 transition hover:bg-surface-2 hover:text-ink disabled:opacity-30 disabled:hover:bg-transparent";
  return (
    <div className="flex shrink-0 items-center gap-0.5">
      <button type="button" className={base} disabled={primero} onClick={clic(onSubir)} aria-label="Subir" title="Subir"><ArrowUp className="size-4" /></button>
      <button type="button" className={base} disabled={ultimo} onClick={clic(onBajar)} aria-label="Bajar" title="Bajar"><ArrowDown className="size-4" /></button>
      <button type="button" className={cx(base, "hover:text-bad")} aria-label="Eliminar" title="Eliminar"
              onClick={clic(() => { if (confirm("¿Eliminar este elemento del CV base? Puedes descartar los cambios si no guardas.")) onQuitar(); })}>
        <Trash2 className="size-4" />
      </button>
    </div>
  );
}

function CampoLogros({ valor, onChange }: { valor: string; onChange: (v: string) => void }) {
  const n = lineas(valor).length;
  return (
    <Campo etiqueta={`Logros (${n})`} ayuda='Uno por línea. Empieza con un verbo en pasado (Diseñé, Implementé...) y, si la tienes, termina con una cifra real. Si solo apoyaste, dilo: "Participé en...".'>
      <textarea className={cx(claseCampo, "min-h-32 leading-relaxed")} value={valor} onChange={(e) => onChange(e.target.value)}
                placeholder={"Diseñé un modelo estrella en SQL Server con 5 dimensiones.\nDesarrollé un dashboard en Power BI con 8 KPIs."} />
    </Campo>
  );
}

function CampoStack({ valor, onChange }: { valor: string; onChange: (v: string) => void }) {
  return (
    <Campo etiqueta="Tecnologías usadas" ayuda="Separadas por comas. Lo que pongas aquí es lo que Pluma puede mencionar sobre este proyecto.">
      <input className={claseCampo} value={valor} placeholder="Python, Power BI, DAX" onChange={(e) => onChange(e.target.value)} />
    </Campo>
  );
}
