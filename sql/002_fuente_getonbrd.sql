-- Fase 6 (Sabueso): Get on Board como fuente de ofertas.
-- Idempotente: se puede correr más de una vez.
INSERT INTO source (nombre) VALUES ('Get on Board')
ON CONFLICT (nombre) DO NOTHING;
