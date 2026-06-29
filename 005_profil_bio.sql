-- =====================================================================
-- Migration 005_profil_bio
-- =====================================================================
-- Documentation de la migration appliquee par database._migrer_v3_phase2()
-- et schema.sql. Ce fichier n'est pas execute automatiquement (voir
-- la note dans 001_initial.sql).
--
-- Objectif : permettre a chaque utilisateur de renseigner une courte
-- biographie sur son profil (voir users.modifier_mon_profil et
-- app.page_parametres).
-- =====================================================================

ALTER TABLE users ADD COLUMN bio TEXT;
