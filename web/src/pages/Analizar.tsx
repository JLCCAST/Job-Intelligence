import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bookmark, BookmarkCheck, ClipboardPaste, Building2, Copy, FilePen, Globe, Languages, Layers, Sparkles, Target } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { aplicarEvento, type Paso } from "../agentes";
import { api, vivo, type ResultadoAnalisis } from "../api";
import LineaAgentes from "../components/LineaAgentes";
import { useAvisos } from "../components/avisos";
import {
  AnilloScore, Aviso, Boton, Campo, Encabezado, Indicador, Insignia, InsigniaEncaje, Seccion, Segmentado, Tarjeta,
  claseCampo, cx, formatoScore,
} from "../components/ui";

// Marcador del navegador ("bookmarklet"): copia la selección (o toda la
// página) al portapapeles y abre la app en una PESTAÑA NUEVA con el link
// de la oferta, así la oferta sigue abierta. No envía formularios ni hace
// peticiones a localhost desde el portal: LinkedIn (y Brave) bloqueaban
// eso en silencio. La copia es síncrona (execCommand) para que la pestaña
// se abra dentro del mismo clic y el navegador no la trate como popup.
const MARCADOR =
  "javascript:(()=>{const t=(String(getSelection())||document.body.innerText).slice(0,60000);" +
  "const a=document.createElement('textarea');a.value=t;a.style.position='fixed';a.style.opacity='0';" +
  "document.body.appendChild(a);a.select();let ok=false;try{ok=document.execCommand('copy')}catch(e){}a.remove();" +
  "if(!ok&&navigator.clipboard)navigator.clipboard.writeText(t).catch(()=>{});" +
  "window.open('http://localhost:8000/analizar?copiada=1&url='+encodeURIComponent(location.href),'_blank')})()";

const MENSAJES: Record<ResultadoAnalisis["registration_status"], { tono: "ok" | "info" | "warn" | "bad"; texto: string }> = {
  saved: { tono: "ok", texto: "Oferta registrada." },
  duplicate: { tono: "info", texto: "Esa oferta ya estaba registrada." },
  offer_closed: { tono: "warn", texto: "La oferta ya no está disponible, así que no se registró." },
  not_attempted: { tono: "bad", texto: "No se pudo analizar la oferta." },
};

type Modo = "Pegar texto" | "Por URL";

export default function Analizar() {
  const [modo, setModo] = useState<Modo>("Pegar texto");
  const [texto, setTexto] = useState("");
  const [url, setUrl] = useState("");
  const [recibida, setRecibida] = useState(false);
  // Oferta copiada con el marcador, esperando que se pegue.
  const [porPegar, setPorPegar] = useState(false);
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const avisar = useAvisos();
  const navegar = useNavigate();

  // Oferta enviada con el marcador: llega como ?pendiente=<id>.
  useEffect(() => {
    const id = params.get("pendiente");
    if (!id) return;
    setParams({}, { replace: true });
    api.pendiente(id)
      .then((o) => { setModo("Pegar texto"); setTexto(o.texto); setUrl(o.url); setRecibida(true); })
      .catch((e) => avisar(e.message, true));
  }, [params, setParams, avisar]);

  // Marcador nuevo: llega como ?copiada=1&url=... y el texto está en el portapapeles.
  useEffect(() => {
    if (!params.get("copiada")) return;
    setModo("Pegar texto");
    setUrl(params.get("url") ?? "");
    setParams({}, { replace: true });
    // Algunos navegadores dejan leer el portapapeles sin un clic; si no, se usa el botón.
    navigator.clipboard?.readText()
      .then((t) => (t.trim() ? (setTexto(t), setRecibida(true)) : setPorPegar(true)))
      .catch(() => setPorPegar(true));
  }, [params, setParams]);

  // Con el cuadro enfocado, Ctrl + V funciona aunque el navegador no deje leer el portapapeles.
  const cuadro = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (porPegar) cuadro.current?.focus();
  }, [porPegar]);

  const pegarCopiada = () =>
    navigator.clipboard.readText()
      .then((t) => { setTexto(t); setPorPegar(false); setRecibida(true); })
      .catch(() => avisar("El navegador no dejó leer el portapapeles. Pega el texto con Ctrl + V.", true));

  // Pasos de los agentes que van llegando en vivo mientras analizan.
  const [pasos, setPasos] = useState<Paso[]>([]);
  const analizar = useMutation({
    mutationFn: () => {
      setPasos([]);
      return vivo.analizar((ev) => setPasos((ps) => aplicarEvento(ps, ev)),
        modo === "Pegar texto" ? texto : undefined, url || undefined);
    },
    onSuccess: () => qc.invalidateQueries(),
  });

  const r = analizar.data;
  const puedeEnviar = modo === "Pegar texto" ? texto.trim().length > 0 : url.trim().length > 0;

  return (
    <div className="aparecer">
      <Encabezado
        seccion="Ofertas"
        titulo="Analizar oferta"
        descripcion="Lupa extrae los requisitos, Archivero la guarda y Balanza calcula qué tanto encajas."
      />

      {porPegar && (
        <div className="mb-5 flex flex-wrap items-center gap-3 rounded-md bg-primary-soft px-4 py-3">
          <p className="flex-1 text-sm text-primary">
            <b>Copiaste una oferta con el marcador.</b> Pulsa <b>Ctrl + V</b> en el cuadro de texto, o usa el botón.
          </p>
          <Boton variante="primario" icono={ClipboardPaste} onClick={pegarCopiada}>Pegar oferta copiada</Boton>
        </div>
      )}
      {recibida && (
        <div className="mb-5">
          <Aviso tono="ok" titulo="Oferta recibida desde el navegador">Revisa el texto y pulsa Analizar.</Aviso>
        </div>
      )}

      <Tarjeta>
        <form
          className="flex flex-col gap-5"
          onSubmit={(e) => { e.preventDefault(); if (puedeEnviar) analizar.mutate(); }}
        >
          <Segmentado etiqueta="Cómo traes la oferta" opciones={["Pegar texto", "Por URL"] as Modo[]} valor={modo} onChange={setModo} />
          {modo === "Pegar texto" ? (
            <>
              <Campo etiqueta="Texto de la oferta">
                <textarea ref={cuadro} className={cx(claseCampo, "min-h-56 resize-y")} value={texto}
                          onChange={(e) => { setTexto(e.target.value); if (e.target.value) setPorPegar(false); }}
                          placeholder="Pega aquí la descripción completa" />
              </Campo>
              <Campo etiqueta="Link de la oferta (opcional)"
                     ayuda="Se guarda para abrirla después, detectar si ya la registraste y saber de qué portal viene. No se descarga.">
                <input className={claseCampo} value={url} onChange={(e) => setUrl(e.target.value)}
                       placeholder="https://www.linkedin.com/jobs/view/..." />
              </Campo>
            </>
          ) : (
            <Campo etiqueta="URL de la oferta"
                   ayuda="LinkedIn, Indeed, Computrabajo y Bumeran no se pueden leer por URL: para esos portales pega el texto.">
              <input className={claseCampo} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />
            </Campo>
          )}
          <div>
            <Boton type="submit" variante="primario" icono={Sparkles} cargando={analizar.isPending} disabled={!puedeEnviar}>
              {analizar.isPending ? "Analizando..." : "Analizar"}
            </Boton>
          </div>
        </form>
      </Tarjeta>

      {pasos.length > 0 && (
        <div className="mt-6">
          <LineaAgentes titulo={analizar.isPending ? "Los agentes están trabajando" : "Así trabajaron los agentes"}
                        pasos={pasos} esperados={analizar.isPending ? ["lupa", "archivero", "balanza"] : []} />
        </div>
      )}
      {analizar.isError && <div className="mt-5"><Aviso tono="bad">{analizar.error.message}</Aviso></div>}
      {r && <Resultado r={r} onAdaptar={(id) => navegar(`/adaptar-cv?job=${id}`)} />}

      <Seccion titulo="Envía ofertas desde el navegador con un clic">
        <Tarjeta className="flex flex-col gap-4">
          <p className="text-sm leading-relaxed text-ink-2">
            Con este marcador, estando en una oferta de LinkedIn, Computrabajo, Bumeran o cualquier portal, un clic la
            manda aquí con su texto y su link. Tú abres la oferta, así que no hay scraping.
          </p>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-ink">
            <li>Copia el código con el botón de abajo.</li>
            <li>En el navegador, clic derecho en la barra de favoritos → <i>Agregar página</i>.</li>
            <li>Nombre: <b>Enviar a Job-Intelligence</b>. En <b>URL</b>, pega el código.</li>
            <li>¿Ya lo tenías? Clic derecho sobre él → <i>Editar</i> y reemplaza la URL por el código nuevo.</li>
          </ol>
          <div className="flex flex-wrap items-center gap-3">
            <Boton icono={Copy} onClick={() => navigator.clipboard.writeText(MARCADOR).then(() => avisar("Código copiado."))}>
              Copiar código del marcador
            </Boton>
            <span className="inline-flex items-center gap-1.5 text-xs text-ink-3"><Bookmark className="size-3.5" />
              Selecciona la descripción de la oferta y haz clic: la copia y abre esta página en otra pestaña. Si no seleccionas nada, copia toda la página.</span>
          </div>
        </Tarjeta>
      </Seccion>
    </div>
  );
}

function Resultado({ r, onAdaptar }: { r: ResultadoAnalisis; onAdaptar: (id: number) => void }) {
  const msg = MENSAJES[r.registration_status];
  const e = r.extraction;
  return (
    <div className="aparecer mt-6 flex flex-col gap-4">
      <Aviso tono={msg.tono} titulo={msg.texto}>{r.registration_status !== "saved" && r.error_detail}</Aviso>
      {r.extraction_status === "partial" && (
        <Aviso tono="warn">El texto extraído es muy corto: puede faltar parte de la oferta. Si es así, pega el texto a mano.</Aviso>
      )}

      {e && (
        <Tarjeta className="flex flex-col gap-6">
          <div className="flex flex-wrap items-center gap-5">
            <AnilloScore score={r.match_score} tamano={84} />
            <div className="min-w-0 flex-1">
              <h2 className="text-xl font-semibold text-ink">{e.job_title}</h2>
              <div className="mt-2 flex flex-wrap gap-2"><InsigniaEncaje score={r.match_score} /></div>
            </div>
            {r.job_id && (r.registration_status === "saved" || r.registration_status === "duplicate") && (
              <Boton variante="primario" icono={FilePen} onClick={() => onAdaptar(r.job_id!)}>Adaptar mi CV</Boton>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Indicador etiqueta="Match Score" valor={formatoScore(r.match_score)} icono={Target} />
            <Indicador etiqueta="Empresa" valor={<span className="text-base">{e.company_name.replace("no_especificado", "No especificada")}</span>} icono={Building2} />
            <Indicador etiqueta="Área" valor={<span className="text-base">{e.area.replace("_", " ")}</span>} icono={Layers} />
            <Indicador etiqueta="Inglés" valor={<span className="text-base capitalize">{e.english_level.replace("no_especificado", "no pide")}</span>} icono={Languages} />
          </div>

          {r.cumple_ingles === false && <Aviso tono="warn">Tu nivel de inglés está por debajo del pedido.</Aviso>}
          {!!r.requisitos_bajo_nivel?.length && (
            <Aviso tono="warn" titulo="Obligatorios donde estás por debajo del nivel pedido">{r.requisitos_bajo_nivel.join(", ")}</Aviso>
          )}
          {!!r.tecnologias_faltantes?.length && <Aviso tono="bad" titulo="Te falta">{r.tecnologias_faltantes.join(", ")}</Aviso>}

          <div>
            <p className="mb-3 text-sm font-semibold text-ink">Requisitos que encontró Lupa</p>
            <div className="overflow-x-auto rounded-md border border-line">
              <table className="w-full text-left text-sm">
                <thead className="bg-surface-2 text-xs text-ink-2 uppercase">
                  <tr>
                    <th className="px-4 py-2.5 font-semibold">Tecnología</th>
                    <th className="px-4 py-2.5 font-semibold">Tipo</th>
                    <th className="px-4 py-2.5 font-semibold">Nivel</th>
                    <th className="px-4 py-2.5 font-semibold">Evidencia en la oferta</th>
                  </tr>
                </thead>
                <tbody>
                  {e.technologies.map((t) => (
                    <tr key={t.name} className="border-t border-line align-top">
                      <td className="px-4 py-2.5 font-medium text-ink">{t.name}</td>
                      <td className="px-4 py-2.5">
                        <Insignia tono={t.requirement_type === "required" ? "info" : "neutro"}>
                          {t.requirement_type === "required" ? "Obligatorio" : "Deseable"}
                        </Insignia>
                      </td>
                      <td className="px-4 py-2.5 text-ink-2 capitalize">{t.level === "unspecified" ? "—" : t.level}</td>
                      <td className="px-4 py-2.5 text-ink-2">"{t.evidence_text}"</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Tarjeta>
      )}

      {!!r.tecnologias_para_revisar?.length && (
        <Aviso titulo="Tecnologías nuevas para revisar en el catálogo">
          <span className="inline-flex items-center gap-1"><BookmarkCheck className="size-3.5" />{r.tecnologias_para_revisar.join(", ")}</span>
        </Aviso>
      )}
      {r.source === "url" && !e && <Aviso tono="info"><Globe className="inline size-3.5" /> Si la página no se pudo leer, pega el texto.</Aviso>}
    </div>
  );
}
