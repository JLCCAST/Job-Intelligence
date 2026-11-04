import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ListChecks } from "lucide-react";
import { api } from "../api";
import { useAvisos } from "../components/avisos";
import { Boton, Cargando, Encabezado, Insignia, Tarjeta, Vacio, plural } from "../components/ui";

export default function Revision() {
  const { data, isLoading } = useQuery({ queryKey: ["revision"], queryFn: api.catalogoRevision });
  const qc = useQueryClient();
  const avisar = useAvisos();
  const aprobar = useMutation({
    mutationFn: ({ id }: { id: number; nombre: string }) => api.aprobar(id),
    onSuccess: (_, v) => { qc.invalidateQueries(); avisar(`${v.nombre} aprobada.`); },
    onError: (e) => avisar(e.message, true),
  });

  return (
    <div className="aparecer">
      <Encabezado
        seccion="Tú"
        titulo="Revisión del catálogo"
        descripcion="Tecnologías que Archivero creó porque no existían en el catálogo y Gemini no estaba seguro (confianza < 0.75). Apruébalas si el nombre y la categoría son correctos."
      />
      {isLoading ? <Cargando /> : !data?.length ? (
        <Vacio icono={ListChecks} titulo="No hay tecnologías pendientes de revisión" />
      ) : (
        <div className="flex flex-col gap-3">
          {data.map((t) => (
            <Tarjeta key={t.technology_id} className="flex flex-wrap items-center gap-4 p-4">
              <p className="min-w-40 flex-1 font-semibold text-ink">{t.tecnologia}</p>
              <Insignia>{t.categoria.replace("_", " ")}</Insignia>
              <span className="text-sm text-ink-2">{plural(t.ofertas, "oferta", "ofertas")}</span>
              <Boton icono={Check} cargando={aprobar.isPending && aprobar.variables?.id === t.technology_id}
                     onClick={() => aprobar.mutate({ id: t.technology_id, nombre: t.tecnologia })}>Aprobar</Boton>
            </Tarjeta>
          ))}
        </div>
      )}
    </div>
  );
}
