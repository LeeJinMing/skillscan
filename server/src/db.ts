import pg from "pg";

const { Pool } = pg;

let pool: pg.Pool | null = null;

/** 获取 Postgres 连接池；无 DATABASE_URL 时返回 null（占位/测试） */
export function getPool(): pg.Pool | null {
  if (pool !== null) return pool;
  const url = process.env.DATABASE_URL;
  if (!url) return null;
  pool = new Pool({ connectionString: url, max: 10 });
  return pool;
}

export type PoolClient = pg.PoolClient;
