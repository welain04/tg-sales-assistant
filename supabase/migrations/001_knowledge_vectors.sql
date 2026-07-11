-- Этап 1: инфраструктура RAG (Supabase pgvector)
-- Выполните в Supabase SQL Editor: https://supabase.com/dashboard/project/_/sql

create extension if not exists vector;

create table if not exists knowledge_files (
    source text primary key,
    file_hash text not null,
    chunk_count integer not null default 0,
    last_indexed_at timestamptz not null default now()
);

create table if not exists knowledge_chunks (
    id uuid primary key default gen_random_uuid(),
    source text not null references knowledge_files(source) on delete cascade,
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    embedding vector(1536),
    content_hash text not null,
    file_hash text not null,
    is_active boolean not null default true,
    indexed_at timestamptz not null default now()
);

create index if not exists knowledge_chunks_source_idx
    on knowledge_chunks (source);

create index if not exists knowledge_chunks_active_idx
    on knowledge_chunks (is_active)
    where is_active = true;

create index if not exists knowledge_chunks_embedding_hnsw_idx
    on knowledge_chunks
    using hnsw (embedding vector_cosine_ops);

create or replace function match_knowledge_chunks(
    query_embedding vector(1536),
    match_count integer default 5,
    filter jsonb default '{}'::jsonb
)
returns table (
    id uuid,
    content text,
    metadata jsonb,
    similarity double precision
)
language sql
stable
as $$
    select
        kc.id,
        kc.content,
        kc.metadata,
        1 - (kc.embedding <=> query_embedding) as similarity
    from knowledge_chunks kc
    where kc.is_active = true
      and kc.metadata @> filter
    order by kc.embedding <=> query_embedding
    limit greatest(match_count, 1);
$$;

comment on table knowledge_files is 'Реестр проиндексированных файлов knowledge/';
comment on table knowledge_chunks is 'Векторные чанки базы знаний для RAG';
comment on function match_knowledge_chunks is 'Поиск релевантных чанков по cosine similarity';
