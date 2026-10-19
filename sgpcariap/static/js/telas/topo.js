import { VERSAO_CONFIG, normalizarConfiguracao, novaConfiguracao } from '../dominio.js';
import { Eventos } from '../estado.js';
import { $, baixar, esc, slug } from '../util.js';
import { Tela } from './base.js';

export class SeletorProvedor extends Tela {
  constructor(contexto) {
    super(contexto);
    this.seletor = $('#sel-provedor');
    this.seletor.addEventListener('change', () => this.trocar(this.seletor.value));
    $('#btn-novo-provedor').addEventListener('click', () => this.criar());
    this.quando([Eventos.PROVEDORES], () => this.renderizar());
    this.renderizar();
  }

  renderizar() {
    this.seletor.innerHTML = this.estado.provedores
      .map((nome) => `<option ${nome === this.estado.provedor ? 'selected' : ''}>${esc(nome)}</option>`).join('');
  }

  async trocar(nome) {
    if (!(await this.encerrarConexao())) {
      this.renderizar();  // volta o seletor para o provedor atual
      return;
    }
    this.estado.trocarProvedor(nome);
    if (!this.config.sgp.url) this.navegacao.mostrar('conexao');
    this.avisos.mostrar(nome);
  }

  pedirNome(pergunta, sugestao = '') {
    const nome = (prompt(pergunta, sugestao) || '').trim();
    if (!nome) return null;
    if (this.estado.existeProvedor(nome)) {
      this.avisos.erro(`“${nome}” já existe`);
      return null;
    }
    return nome;
  }

  async criar() {
    const nome = this.pedirNome('Nome do provedor');
    if (!nome) return;
    const nova = novaConfiguracao(nome);
    if (this.config.grupos.length && confirm('Copiar os grupos do provedor atual?')) {
      nova.grupos = structuredClone(this.config.grupos);
    }
    if (!(await this.encerrarConexao())) return;
    this.estado.criarProvedor(nome, nova);
    this.navegacao.mostrar('conexao');
  }

  renomear() {
    const nome = this.pedirNome('Novo nome', this.estado.provedor);
    if (nome) this.estado.renomearProvedor(nome);
  }

  excluir() {
    if (this.estado.provedores.length === 1) {
      this.avisos.erro('Não dá para excluir o único provedor');
      return;
    }
    if (confirm(`Excluir “${this.estado.provedor}”? A configuração dele será apagada.`)) {
      this.estado.excluirProvedor();
    }
  }
}

export class ArquivoConfiguracao extends Tela {
  constructor(contexto, seletorProvedor) {
    super(contexto);
    this.seletorProvedor = seletorProvedor;
    $('#btn-exportar').addEventListener('click', () => this.exportar());
    $('#btn-importar input').addEventListener('change', (evento) => this.importar(evento.target));
  }

  exportar() {
    const nome = `sgp-cariap-${slug(this.config.provedor || 'provedor')}-${new Date().toISOString().slice(0, 10)}.json`;
    baixar(nome, JSON.stringify(this.config, null, 2), 'application/json');
  }

  async importar(campo) {
    const arquivo = campo.files[0];
    campo.value = '';
    if (!arquivo) return;
    try {
      const dados = JSON.parse(await arquivo.text());
      if (!dados.versao || dados.versao > VERSAO_CONFIG) throw new Error('arquivo não reconhecido');
      let nome = dados.provedor || arquivo.name.replace(/\.json$/i, '');
      if (this.estado.existeProvedor(nome) && !confirm(`Substituir a configuração de “${nome}”?`)) {
        nome = this.seletorProvedor.pedirNome('Nome do provedor importado', `${nome} (importado)`);
        if (!nome) return;
      }
      if (this.estado.existeProvedor(nome)) {
        this.estado.trocarProvedor(nome);
        this.estado.substituir(dados);
      } else {
        this.estado.criarProvedor(nome, normalizarConfiguracao(dados, nome));
      }
      this.avisos.mostrar(`“${nome}” importado`);
    } catch (erro) {
      this.avisos.erro(`Não foi possível abrir (${erro.message})`);
    }
  }
}

export class MenuAjuda extends Tela {
  constructor(contexto, { tour, seletorProvedor }) {
    super(contexto);
    this.botao = $('#btn-ajuda');
    this.menu = $('#menu-ajuda');
    const acoes = {
      secao: () => tour.explicar(this.navegacao.atual),
      completo: () => tour.completo(),
      renomear: () => seletorProvedor.renomear(),
      excluir: () => seletorProvedor.excluir(),
      limpar: () => this.limpar(),
    };
    this.botao.addEventListener('click', () => this.#alternar(this.menu.hidden));
    this.menu.addEventListener('click', (evento) => {
      const acao = acoes[evento.target.dataset.tour];
      this.#alternar(false);
      acao?.();
    });
    document.addEventListener('click', (evento) => {
      if (!evento.target.closest('.ajuda')) this.#alternar(false);
      const explicar = evento.target.closest('[data-explicar]');
      if (explicar) tour.explicar(explicar.dataset.explicar);
    });
  }

  mostrarVersao(versao, pastaDados) {
    $('#versao').textContent = `Versão ${versao}`;
    $('#versao').dataset.dica = `Registros em ${pastaDados}`;
  }

  limpar() {
    if (confirm(`Apagar grupos e filtros de “${this.estado.provedor}”?`)) {
      this.estado.substituir({ ...novaConfiguracao(this.estado.provedor), sgp: this.config.sgp });
    }
  }

  #alternar(aberto) {
    this.menu.hidden = !aberto;
    this.botao.setAttribute('aria-expanded', String(aberto));
  }
}
