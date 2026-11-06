/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 后端地址。留空则使用同源相对路径（开发期由 Vite 代理） */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}