import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Download, FileText, Sparkles, Send, Stamp } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { aplicarEvento, type EventoAgente, type Paso } from "../agentes";
import { api, urlArchivo, vivo, type CambioCV, type FlujoCV, type Respuesta } from "../api";
import LineaAgentes from "../components/LineaAgentes";
import {
  Aviso, Boton, Campo, Cargando, Encabezado, Insignia, Tarjeta, claseCampo, cx, formatoScore, plural,
} from "../components/ui";

const PASOS = ["Elegir oferta", "Responder preguntas", "Revisar cambios", "Descargar documentos"];

function Pasos({ actual }: { actual: number }) {
  return (
    <ol className="mb-7 flex flex-wrap items-center gap-2">
      {PASOS.map((p, i) => (
        <li key={p} className="flex items-center gap-2">
          <span className={cx(
            "flex size-7 items-center justify-center rounded-full text-xs font-semibold",
            i < actual ? "bg-ok text-white" : i === actual ? "bg-primary text-white" : "bg-surface-2 text-ink-3",
          )}>
            {i < actual ? <Check className="size-4" /> : i + 1}
          </span>
          <span className={cx("text-sm font-medium", i === actual ? "text-ink" : "text-ink-2")}>{p}</span>
          {i < PASOS.length - 1 && <span className="mx-1 h-px w-8 bg-line" aria-hidden />}
        </li>
      ))}
    </ol>
  );
}

export default function AdaptarCV() {
  const [params, setParams] = useSearchParams();
  const { data: ofertas, isLoading } = useQuery({ queryKey: ["ofertas"], queryFn: api.ofertas });
  const [flujo, setFlujo] = useState<FlujoCV | null>(null);
  // Cuántos cambios revisaste (para el resumen final: el flujo terminado ya no trae la lista).
  const [revisados, setRevisados] = useState<number | null>(null);
  const qc = useQueryClient();
  const terminado = (f: FlujoCV) => !f.esperando_respuestas && !f.esperando_revision;

  const jobParam = Number(params.get("job"));
  const jobId = ofertas?.some((o) => o.job_id === jobParam) ? jobParam : ofertas?.[0]?.job_id;

  // La línea de agentes acompaña todo el flujo: inicio, pausa y respuesta.
  const [pasos, setPasos] = useState<Paso[]>([]);
  const [esperados, setEsperados] = useState<string[]>([]);
  const alEvento = (ev: EventoAgente) => setPasos((ps) => aplicarEvento(ps, ev));

  const iniciar = useMutation({
    mutationFn: () => {
      setPasos([]);
      setRevisados(null);
      setEsperados(["balanza", "pregunton", "pluma", "validador", "notario", "imprenta"]);
      return vivo.iniciarCV(alEvento, jobId!);
    },
    onSettled: () => setEsperados([]),
    onSuccess: (f) => { setFlujo(f); if (terminado(f)) qc.invalidateQueries({ queryKey: ["cvs"] }); },
  });

  if (isLoading) return <Cargando />;
  if (!ofertas?.length) return <Aviso>Aún no tienes ofertas registradas. Analiza una en «Analizar oferta».</Aviso>;

  const paso = !flujo ? 0 : flujo.esperando_respuestas ? 1 : flujo.esperando_revision ? 2 : 4;
  const tituloLinea = esperados.length
    ? "Los agentes están trabajando"
    : flujo?.esperando_respuestas ? "Preguntón pausó el flujo"
    : flujo?.esperando_revision ? "Notario espera tu revisión"
    : "Así trabajaron los agentes";
  const alTerminar = (f: FlujoCV) => {
    setEsperados([]);
    setFlujo(f);
    if (terminado(f)) qc.invalidateQueries({ queryKey: ["cvs"] });
  };

  return (
    <div className="aparecer">
      <Encabezado
        seccion="Ofertas"
        titulo="Adaptar CV"
        descripcion="Preguntón te consulta lo que falta, Pluma adapta tu CV sin inventar nada, Notario te explica cada cambio para que decidas e Imprenta genera el CV y el informe de brechas en Word."
      />
      <Pasos actual={paso} />

      <Tarjeta className="flex flex-col gap-4">
        <Campo etiqueta="Oferta">
          <select className={claseCampo} value={jobId}
                  onChange={(e) => { setParams({ job: e.target.value }); setFlujo(null); setPasos([]); setRevisados(null); iniciar.reset(); }}>
            {ofertas.map((o) => (
              <option key={o.job_id} value={o.job_id}>{o.puesto} — {o.empresa} ({formatoScore(o.match_score)})</option>
            ))}
          </select>
        </Campo>
        <div>
          <Boton variante="primario" icono={Sparkles} cargando={iniciar.isPending} onClick={() => { setFlujo(null); iniciar.mutate(); }}>
            {iniciar.isPending ? "Preparando..." : flujo ? "Adaptar de nuevo" : "Adaptar CV"}
          </Boton>
        </div>
        {iniciar.isError && <Aviso tono="bad">{iniciar.error.message}</Aviso>}
      </Tarjeta>

      {pasos.length > 0 && (
        <div className="mt-6">
          <LineaAgentes titulo={tituloLinea} pasos={pasos} esperados={esperados} />
        </div>
      )}
      {flujo?.esperando_respuestas && (
        <Preguntas
          key={flujo.thread_id}
          flujo={flujo} alEvento={alEvento}
          alEmpezar={() => setEsperados(["pluma", "validador", "notario", "imprenta"])}
          alFallar={() => setEsperados([])}
          onListo={alTerminar}
        />
      )}
      {flujo?.esperando_revision && (
        <Revision
          key={flujo.thread_id}
          flujo={flujo} alEvento={alEvento}
          alEmpezar={() => { setRevisados(flujo.cambios.length); setEsperados(["notario", "imprenta"]); }}
          alFallar={() => setEsperados([])}
          onListo={alTerminar}
        />
      )}
      {flujo && terminado(flujo) && <Documentos flujo={flujo} revisados={revisados} />}
    </div>
  );
}

// ---------- Revisión de cambios (Notario) ----------

// Por debajo de esto, mezclar palabras quitadas y agregadas ya no se lee: se muestra antes / ahora.
const SIMILITUD_MINIMA = 0.5;

function TextoCambio({ cambio, aceptado }: { cambio: CambioCV; aceptado: boolean }) {
  if (!aceptado) {
    return <p className="text-sm leading-relaxed text-ink">{cambio.original}</p>;
  }
  if ((cambio.similitud ?? 1) < SIMILITUD_MINIMA) {
    return (
      <div className="flex flex-col gap-3 text-sm leading-relaxed">
        <div>
          <p className="mb-1 text-xs font-medium text-ink-3">Antes (tu texto)</p>
          <p className="border-l-2 border-bad/50 pl-3 text-ink-2"><del className="no-underline">{cambio.original}</del></p>
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-ink-3">Ahora (reescrito casi por completo)</p>
          <p className="border-l-2 border-ok/60 pl-3 text-ink"><ins className="no-underline">{cambio.nuevo}</ins></p>
        </div>
      </div>
    );
  }
  return (
    <p className="text-sm leading-relaxed text-ink">
      {cambio.diferencias.map((d, i) =>
        d.tipo === "quitado" ? (
          <del key={i} className="rounded-sm bg-bad-soft px-0.5 text-bad decoration-1">{d.texto}</del>
        ) : d.tipo === "agregado" ? (
          <ins key={i} className="rounded-sm bg-ok-soft px-0.5 text-ok no-underline">{d.texto}</ins>
        ) : (
          <span key={i}>{d.texto}</span>
        ),
      )}
    </p>
  );
}

function TarjetaCambio({ cambio, aceptado, alCambiar }: { cambio: CambioCV; aceptado: boolean; alCambiar: (v: boolean) => void }) {
  return (
    <Tarjeta className={cx("flex flex-col gap-3", !aceptado && "bg-surface-2")}>
      <TextoCambio cambio={cambio} aceptado={aceptado} />
      {!aceptado && <p className="text-xs text-ink-3">Rechazado: se mantiene tu texto original.</p>}

      <div className="flex gap-2 border-t border-line pt-3 text-sm">
        <Stamp className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden />
        <div className="flex flex-col gap-1.5">
          <p className="text-ink-2">
            <span className="font-medium text-ink">{cambio.motivo_de === "notario" ? "Notario: " : "Motivo automático: "}</span>
            {cambio.motivo}
          </p>
          {cambio.requisitos.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-ink-3">Atiende:</span>
              {cambio.requisitos.map((r) => <Insignia key={r} tono="info">{r}</Insignia>)}
            </div>
          )}
        </div>
      </div>
      {cambio.atencion && <Aviso tono="warn" titulo="Notario sugiere revisar">{cambio.atencion}</Aviso>}
      {cambio.alerta && <Aviso tono="bad" titulo="La verificación encontró un problema en el motivo">{cambio.alerta}</Aviso>}

      <div className="inline-flex w-fit rounded-md border border-line p-1" role="radiogroup" aria-label="Decisión sobre este cambio">
        {[true, false].map((v) => (
          <button key={String(v)} type="button" role="radio" aria-checked={aceptado === v}
                  onClick={() => alCambiar(v)}
                  className={cx("rounded px-4 py-1.5 text-sm font-medium",
                    aceptado === v ? (v ? "bg-ok-soft text-ok" : "bg-bad-soft text-bad") : "text-ink-2 hover:text-ink")}>
            {v ? "Aceptar" : "Rechazar"}
          </button>
        ))}
      </div>
    </Tarjeta>
  );
}

const SECCION: Record<CambioCV["seccion"], string> = { perfil: "Perfil", experiencia: "Experiencia", proyectos: "Proyecto" };

function Revision({ flujo, onListo, alEvento, alEmpezar, alFallar }: {
  flujo: FlujoCV; onListo: (f: FlujoCV) => void; alEvento: (ev: EventoAgente) => void;
  alEmpezar: () => void; alFallar: () => void;
}) {
  // Por defecto se acepta todo: rechazas lo que no te convence.
  const [rechazados, setRechazados] = useState<Set<string>>(new Set());
  const enviar = useMutation({
    mutationFn: () => { alEmpezar(); return vivo.revisar(alEvento, flujo.thread_id, [...rechazados]); },
    onSuccess: onListo,
    onError: alFallar,
  });
  const decidir = (id: string, aceptar: boolean) =>
    setRechazados((s) => { const n = new Set(s); if (aceptar) n.delete(id); else n.add(id); return n; });

  // Agrupa por ítem (perfil, cada experiencia, cada proyecto), en el orden del CV.
  const grupos: { titulo: string; seccion: string; cambios: CambioCV[] }[] = [];
  for (const c of flujo.cambios) {
    const g = grupos.find((x) => x.titulo === c.item && x.seccion === c.seccion);
    if (g) g.cambios.push(c);
    else grupos.push({ titulo: c.item, seccion: c.seccion, cambios: [c] });
  }
  const total = flujo.cambios.length;
  const aceptados = total - rechazados.size;

  return (
    <div className="aparecer mt-6">
      <h2 className="text-base font-semibold text-ink">Revisa lo que cambió la IA</h2>
      <p className="mt-1 mb-4 text-sm text-ink-2">
        Lo quitado aparece <del className="bg-bad-soft px-0.5 text-bad">tachado</del> y lo nuevo <ins className="bg-ok-soft px-0.5 text-ok no-underline">resaltado</ins>.
        Lo que rechaces vuelve a tu texto original. El Word final sale limpio, sin marcas.
      </p>

      <div className="flex flex-col gap-3">
        {flujo.notario_error && (
          <Aviso tono="warn" titulo="Notario no estuvo disponible">
            Gemini no respondió, así que los motivos son automáticos: dicen qué términos se agregaron, no por qué.
          </Aviso>
        )}
        {flujo.estructura.length > 0 && (
          <Aviso tono="info" titulo="Además, Pluma decidió (sin cambiar textos)">
            <ul className="list-disc pl-5">{flujo.estructura.map((e) => <li key={e}>{e}</li>)}</ul>
          </Aviso>
        )}
      </div>

      <div className="sticky top-0 z-10 mt-4 flex flex-wrap items-center justify-between gap-3 border-b border-line bg-bg py-3">
        <p className="text-sm text-ink-2">
          <span className="font-mono font-semibold tabular-nums text-ink">{aceptados}</span> de {plural(total, "cambio aceptado", "cambios aceptados")}
        </p>
        <div className="flex gap-2">
          <Boton variante="fantasma" onClick={() => setRechazados(new Set())}>Aceptar todo</Boton>
          <Boton variante="fantasma" onClick={() => setRechazados(new Set(flujo.cambios.map((c) => c.id)))}>Rechazar todo</Boton>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-6">
        {grupos.map((g) => (
          <section key={g.seccion + g.titulo}>
            <p className="mb-2 text-sm">
              <span className="text-ink-3">{SECCION[g.seccion as CambioCV["seccion"]]} / </span>
              <span className="font-semibold text-ink">{g.titulo}</span>
            </p>
            <div className="flex flex-col gap-3">
              {g.cambios.map((c) => (
                <TarjetaCambio key={c.id} cambio={c} aceptado={!rechazados.has(c.id)} alCambiar={(v) => decidir(c.id, v)} />
              ))}
            </div>
          </section>
        ))}
      </div>

      <div className="mt-6 flex flex-col gap-3">
        {enviar.isError && <Aviso tono="bad">{enviar.error.message}</Aviso>}
        <div>
          <Boton variante="primario" icono={FileText} cargando={enviar.isPending} onClick={() => enviar.mutate()}>
            {enviar.isPending ? "Imprenta está generando tu CV..." : "Generar CV con los cambios aceptados"}
          </Boton>
        </div>
      </div>
    </div>
  );
}

function Preguntas({ flujo, onListo, alEvento, alEmpezar, alFallar }: {
  flujo: FlujoCV; onListo: (f: FlujoCV) => void; alEvento: (ev: EventoAgente) => void;
  alEmpezar: () => void; alFallar: () => void;
}) {
  const [respuestas, setRespuestas] = useState<Respuesta[]>(
    flujo.preguntas.map((p) => ({ tecnologia: p.tecnologia, la_tengo: false, nivel: "basico", donde: "", detalle: "" })),
  );
  const enviar = useMutation({
    mutationFn: () => { alEmpezar(); return vivo.responder(alEvento, flujo.thread_id, respuestas.map((r) =>
      r.la_tengo
        ? { tecnologia: r.tecnologia, la_tengo: true, nivel: r.nivel, donde: r.donde?.trim(), detalle: r.detalle?.trim() || undefined }
        : { tecnologia: r.tecnologia, la_tengo: false }));
    },
    onSuccess: onListo,
    onError: alFallar,
  });
  const actualizar = (i: number, cambio: Partial<Respuesta>) =>
    setRespuestas((rs) => rs.map((r, j) => (j === i ? { ...r, ...cambio } : r)));
  const faltaDonde = respuestas.find((r) => r.la_tengo && !r.donde?.trim());

  return (
    <div className="aparecer mt-6">
      <h2 className="text-base font-semibold text-ink">Antes de escribir, unas preguntas</h2>
      <p className="mt-1 mb-4 text-sm text-ink-2">
        Solo lo que confirmes con «Sí» puede aparecer en tu CV. Tus respuestas se guardan y no se vuelven a preguntar.
      </p>
      <div className="flex flex-col gap-3">
        {flujo.preguntas.map((p, i) => {
          const r = respuestas[i];
          return (
            <Tarjeta key={p.tecnologia} className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-ink">{p.tecnologia}</span>
                <Insignia tono={p.requirement_type === "required" ? "warn" : "neutro"}>
                  {p.requirement_type === "required" ? "Obligatorio" : "Deseable"}
                </Insignia>
              </div>
              <p className="text-sm text-ink-2">{p.texto}</p>
              <div className="inline-flex w-fit rounded-md border border-line p-1" role="radiogroup" aria-label={`¿Tienes ${p.tecnologia}?`}>
                {[false, true].map((v) => (
                  <button key={String(v)} type="button" role="radio" aria-checked={r.la_tengo === v}
                          onClick={() => actualizar(i, { la_tengo: v })}
                          className={cx("rounded px-4 py-1.5 text-sm font-medium",
                            r.la_tengo === v ? (v ? "bg-ok-soft text-ok" : "bg-surface-2 text-ink") : "text-ink-2")}>
                    {v ? "Sí, lo tengo" : "No"}
                  </button>
                ))}
              </div>
              {r.la_tengo && (
                <div className="aparecer grid gap-3 sm:grid-cols-3">
                  <Campo etiqueta="Nivel">
                    <select className={claseCampo} value={r.nivel} onChange={(e) => actualizar(i, { nivel: e.target.value as Respuesta["nivel"] })}>
                      <option value="basico">Básico</option><option value="intermedio">Intermedio</option><option value="avanzado">Avanzado</option>
                    </select>
                  </Campo>
                  <Campo etiqueta="¿Dónde lo usaste?">
                    <input className={claseCampo} value={r.donde} placeholder="Proyecto, trabajo o curso"
                           onChange={(e) => actualizar(i, { donde: e.target.value })} />
                  </Campo>
                  <Campo etiqueta="¿Qué hiciste? (opcional)">
                    <input className={claseCampo} value={r.detalle} onChange={(e) => actualizar(i, { detalle: e.target.value })} />
                  </Campo>
                </div>
              )}
            </Tarjeta>
          );
        })}
      </div>
      <div className="mt-4 flex flex-col gap-3">
        {faltaDonde && <p className="text-sm text-warn">Indica dónde usaste {faltaDonde.tecnologia}, o marca «No».</p>}
        {enviar.isError && <Aviso tono="bad">{enviar.error.message}</Aviso>}
        <div>
          <Boton variante="primario" icono={Send} cargando={enviar.isPending} disabled={!!faltaDonde} onClick={() => enviar.mutate()}>
            {enviar.isPending ? "Pluma está adaptando tu CV..." : "Enviar respuestas y adaptar"}
          </Boton>
        </div>
      </div>
    </div>
  );
}

function Documentos({ flujo, revisados }: { flujo: FlujoCV; revisados: number | null }) {
  const rechazados = flujo.rechazados?.length ?? 0;
  return (
    <div className="aparecer mt-6 flex flex-col gap-4">
      {flujo.usa_texto_de_pluma ? (
        <Aviso tono="ok" titulo="Tu CV está listo">
          Pluma lo adaptó y el validador lo aprobó.
          {revisados != null && revisados > 0 && (
            <> Aceptaste {revisados - rechazados} de {plural(revisados, "cambio", "cambios")} de la IA{rechazados > 0 && "; lo rechazado mantiene tu texto original"}.</>
          )}
        </Aviso>
      ) : (
        <Aviso tono="warn" titulo="Se usaron tus textos originales">
          El texto adaptado no pasó el validador, así que el CV usa tus bullets originales ordenados por relevancia.
          {flujo.avisos.length > 0 && <ul className="mt-1 list-disc pl-5">{flujo.avisos.map((a) => <li key={a}>{a}</li>)}</ul>}
        </Aviso>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { ruta: flujo.ruta_cv, titulo: "CV adaptado", desc: "Listo para enviar." },
          { ruta: flujo.ruta_brechas, titulo: "Informe de brechas", desc: "Qué te falta y cómo abordarlo." },
        ].map((d) => d.ruta && (
          <a key={d.titulo} href={urlArchivo(d.ruta)}
             className="group flex items-center gap-4 rounded-md border border-line bg-surface p-5 transition hover:border-primary/40">
            <span className="flex size-12 items-center justify-center rounded-md bg-primary-soft text-primary"><FileText className="size-6" /></span>
            <div className="flex-1">
              <p className="font-semibold text-ink">{d.titulo}</p>
              <p className="text-sm text-ink-2">{d.desc}</p>
            </div>
            <Download className="size-5 text-ink-3 transition group-hover:text-primary" />
          </a>
        ))}
      </div>
      <p className="text-xs text-ink-3">Las versiones anteriores siguen disponibles en «Postulaciones».</p>
    </div>
  );
}
