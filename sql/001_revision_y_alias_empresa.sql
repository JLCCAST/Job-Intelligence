-- Cambios que se hicieron directo en Supabase (Fases 4 y 5) y no
-- habían quedado en el repo. Sin esto, un clon nuevo no funciona:
-- matcher.py y repository.py ya los usan.
-- Idempotente: se puede correr sobre una base que ya los tiene.

-- Tecnologías creadas por el pipeline con baja confianza (< 0.75)
-- quedan marcadas para revisarlas en la app ("Revisión del catálogo").
ALTER TABLE technology
    ADD COLUMN IF NOT EXISTS necesita_revision BOOLEAN NOT NULL DEFAULT FALSE;

-- Variantes de nombre de una misma empresa ("Alicorp S.A.A." -> "Alicorp"),
-- mismo patrón que technology_alias.
CREATE TABLE IF NOT EXISTS company_alias (
    alias_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES company(company_id),
    alias_texto     VARCHAR(200) NOT NULL UNIQUE
);
