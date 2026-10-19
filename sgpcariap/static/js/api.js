// o servidor manda as mensagens em minúsculas
export class ErroApi extends Error {
  constructor(mensagem) {
    super(mensagem.charAt(0).toUpperCase() + mensagem.slice(1));
  }
}

export class ClienteApi {
  #get(caminho, parametros = {}) {
    const consulta = new URLSearchParams(parametros).toString();
    return this.#requisitar(consulta ? `${caminho}?${consulta}` : caminho, {});
  }

  #post(caminho, corpo = {}) {
    return this.#requisitar(caminho, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corpo),
    });
  }

  async #requisitar(caminho, opcoes) {
    let resposta;
    try {
      resposta = await fetch(caminho, opcoes);
    } catch {
      throw new ErroApi('O assistente não responde. Confira se a janela do terminal continua aberta.');
    }
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok) throw new ErroApi(dados.erro || `HTTP ${resposta.status}`);
    return dados;
  }

  status() { return this.#get('/api/status'); }
  conectar(dados) { return this.#post('/api/conectar', dados); }
  desconectar() { return this.#post('/api/desconectar'); }
  planos(reler = false) { return this.#get('/api/planos', reler ? { reler: 1 } : {}); }
  loteOpcoes() { return this.#get('/api/lote/opcoes'); }
  loteMontar(config) { return this.#post('/api/lote/montar', { config }); }
  loteIniciar(config, selecionados) { return this.#post('/api/lote/iniciar', { config, selecionados }); }
  tarefa(id) { return this.#get('/api/job', { id }); }
  controlarTarefa(id, acao) { return this.#post('/api/job/controle', { id, acao }); }
}
