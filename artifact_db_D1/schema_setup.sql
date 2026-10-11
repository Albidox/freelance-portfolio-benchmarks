-- PostgreSQL 18 Sandbox Setup for Artifact D1
-- Target Database: 127.0.0.1:5433 / artifact_d1_db
-- User: postgres

-- Drop previous sandbox database if present
DROP DATABASE IF EXISTS artifact_d1_db WITH (FORCE);

-- Create isolated sandbox database
CREATE DATABASE artifact_d1_db WITH OWNER = postgres;

-- Connect to sandbox database
\connect artifact_d1_db

-- Extensions and schema setup
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS public;
