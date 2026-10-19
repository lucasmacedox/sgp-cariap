export class Tela {
  constructor(contexto) {
    this.estado = contexto.estado;
    this.api = contexto.api;
    this.navegacao = contexto.navegacao;
    this.avisos = contexto.avisos;
  }

  get config() {
    return this.estado.config;
  }

  quando(eventos, acao) {
    for (const evento of eventos) this.estado.addEventListener(evento, () => acao());
  }

  // false se o servidor recusar (execução em andamento); servidor fora do ar conta como desconectado
  async encerrarConexao() {
    if (!this.estado.conexao) return true;
    try {
      await this.api.desconectar();
    } catch (erro) {
      if (!erro.message.startsWith('O assistente não responde')) {
        this.avisos.erro(erro.message);
        return false;
      }
    }
    this.estado.definirConexao(null);
    return true;
  }
}
