import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Download, FileText, Sparkles, Send } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { aplicarEvento, type EventoAgente, type Paso } from "../agentes";
import { api, urlArchivo, vivo, type FlujoCV, type Respuesta } from "../api";
import LineaAgentes from "../components/LineaAgentes";
import {
  Aviso, Boton, Campo, Cargando, Encabezado, Insignia, Tarjeta, claseCampo, cx, formatoScore,
} from "../components/ui";

const PASOS = ["Elegir oferta", "Responder preguntas", "Descargar documentos"];

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
  const qc = useQueryClient();

  const jobParam = Number(params.get("job"));
  const jobId = ofertas?.some((o) => o.job_id === jobParam) ? jobParam : ofertas?.[0]?.job_id;

  // La línea de agentes acompaña todo el flujo: inicio, pausa y respuesta.
  const [pasos, setPasos] = useState<Paso[]>([]);
  const [esperados, setEsperados] = useState<string[]>([]);
  const alEvento = (ev: EventoAgente) => setPasos((ps) => aplicarEvento(ps, ev));

  const iniciar = useMutation({
    mutationFn: () => {
      setPasos([]);
      setEsperados(["balanza", "pregunton", "pluma", "validador", "imprenta"]);
      return vivo.iniciarCV(alEvento, jobId!);
    },
    onSettled: () => setEsperados([]),
    onSuccess: (f) => { setFlujo(f); if (!f.esperando_respuestas) qc.invalidateQueries({ queryKey: ["cvs"] }); },
  });

  if (isLoading) return <Cargando />;
  if (!ofertas?.length) return <Aviso>Aún no tienes ofertas registradas. Analiza una en «Analizar oferta».</Aviso>;

  const paso = !flujo ? 0 : flujo.esperando_respuestas ? 1 : 3;

  return (
    <div className="aparecer">
      <Encabezado
        seccion="Ofertas"
        titulo="Adaptar CV"
        descripcion="Preguntón te consulta lo que falta, Pluma adapta tu CV sin inventar nada e Imprenta genera el CV y el informe de brechas en Word."
      />
      <Pasos actual={paso} />

      <Tarjeta className="flex flex-col gap-4">
        <Campo etiqueta="Oferta">
          <select className={claseCampo} value={jobId}
                  onChange={(e) => { setParams({ job: e.target.value }); setFlujo(null); setPasos([]); iniciar.reset(); }}>
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
          <LineaAgentes
            titulo={esperados.length ? "Los agentes están trabajando" : flujo?.esperando_respuestas ? "Preguntón pausó el flujo" : "Así trabajaron los agentes"}
            pasos={pasos} esperados={esperados}
          />
        </div>
      )}
      {flujo?.esperando_respuestas && (
        <Preguntas
          flujo={flujo} alEvento={alEvento}
          alEmpezar={() => setEsperados(["pluma", "validador", "imprenta"])}
          alFallar={() => setEsperados([])}
          onListo={(f) => { setEsperados([]); setFlujo(f); qc.invalidateQueries({ queryKey: ["cvs"] }); }}
        />
      )}
      {flujo && !flujo.esperando_respuestas && <Documentos flujo={flujo} />}
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

function Documentos({ flujo }: { flujo: FlujoCV }) {
  return (
    <div className="aparecer mt-6 flex flex-col gap-4">
      {flujo.usa_texto_de_pluma ? (
        <Aviso tono="ok" titulo="Tu CV está listo">Pluma lo adaptó y el validador lo aprobó.</Aviso>
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
