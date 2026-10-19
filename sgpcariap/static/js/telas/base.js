// Base das telas: acesso ao contexto compartilhado e assinatura de eventos.

export class Tela {
  /**
   * @param {object} contexto
   * @param {import('../estado.js').Estado} contexto.estado
   * @param {import('../api.js').ClienteApi} contexto.api
   * @param {import('../navegacao.js').Navegacao} contexto.navegacao
   * @param {import('../util.js').Avisos} contexto.avisos
   */
  constructor(contexto) {
    this.contexto = contexto;
    this.estado = contexto.estado;
    this.api = contexto.api;
    this.navegacao = contexto.navegacao;
    this.avisos = contexto.avisos;
  }

  get config() {
    return this.estado.config;
  }

  /** Executa `acao` sempre que qualquer um dos eventos do estado ocorrer. */
  quando(eventos, acao) {
    for (const evento of eventos) this.estado.addEventListener(evento, () => acao());
  }
}
